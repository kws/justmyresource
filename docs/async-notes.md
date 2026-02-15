# Async & Online I/O Considerations (Deferred)

This document summarizes async-related concepts that were **removed** from the main architecture (see [architecture.md](architecture.md)) and explores future options if async support becomes necessary. The current architecture is **synchronous-only** by design.

## Current Decision

As of the current architecture:

- **Registry and packs are synchronous**: All methods (`get_resource`, `list_resources`) are blocking operations.
- **Online packs use blocking I/O**: Packs that fetch from APIs perform blocking network calls inside their methods (e.g., using `requests` or `httpx.Client`).
- **ResourceContent.data is required**: The `data: bytes` field always contains the actual resource bytes.
- **No async dependencies**: The core library has zero dependencies and avoids `asyncio`, `httpx.AsyncClient`, or any async frameworks.

This design prioritizes simplicity, predictability, and broad compatibility (CLI tools, scripts, web frameworks, GUIs) over non-blocking I/O.

## Chosen Strategy: Internal Kernel (Documented Now, Extractable Later)

The current architecture uses an **"Internal Kernel"** pattern that separates pure resolution logic from I/O operations. This design enables future async support within the same package without code duplication or a separate library.

### Current Implementation

The resolution logic in `ResourceRegistry._resolve_name()` is intentionally a **pure function**:
- **No I/O**: Performs no filesystem access, network calls, environment variable reads, or discovery operations
- **Reads only in-memory state**: Accesses only `_packs`, `_prefixes`, `_collisions`, and `_default_prefix`
- **Deterministic and testable**: Can be tested in isolation with pre-seeded state

The execution flow follows a clear separation:
1. **`discover()`** - I/O phase: Loads packs from EntryPoints (filesystem, environment)
2. **`_resolve_name()`** - Pure kernel: Resolves query to `(qualified_pack_name, resource_name)` using only in-memory state
3. **`pack.get_resource()`** - Pack I/O: Pack-specific I/O (filesystem, network, etc.)

```mermaid
flowchart TD
  discover[discover()\nI/O: entry points, env] --> state[Registry_state\n_packs/_prefixes/_collisions/_default_prefix]
  state --> resolve[_resolve_name()\nPure kernel\nno I/O]
  resolve --> execute[pack.get_resource()\nI/O: filesystem/network]
```

### Future Migration Path

When async support becomes necessary, the kernel can be extracted without logic duplication:

1. **Extract kernel** into `justmyresource.resolution` module:
   - Create `RegistryState` dataclass (immutable snapshot of registry state)
   - Extract `resolve_name(state: RegistryState, query: str) -> tuple[str, str]` as a module-level pure function

2. **Refactor `ResourceRegistry`** to use the extracted kernel:
   - `_resolve_name()` becomes a thin wrapper: `resolve_name(self._state, query)`

3. **Add `AsyncResourceRegistry`** (in `justmyresource.async_registry` or `justmyresource.async`):
   - Reuses the **exact same** `resolve_name()` kernel function
   - Only differs in execution: `await pack.aget_resource()` or `await asyncio.to_thread(pack.get_resource)`

**Key Advantage**: Resolution logic (prefix handling, collision detection, FQN parsing, defaults) is written **once** and shared between sync and async implementations. Only the I/O boundaries change.

### Critical Invariant

The `_resolve_name()` method **must remain pure**. Any changes that introduce I/O, side effects, or external dependencies will break the extraction path and force logic duplication. This invariant is documented in the method's docstring and should be enforced by tests.

## Async Concepts Removed from Architecture

The following async-related features were considered but **removed** from the main architecture:

### 1. AsyncResourcePack Protocol

**What it was**: A protocol for packs with async `get_resource()` methods:
```python
class AsyncResourcePack(Protocol):
    async def get_resource(self, name: str) -> ResourceContent: ...
```

**Why removed**: 
- Introduces "function coloring" (sync vs async call sites)
- Requires event loop management and sync↔async bridging
- Adds complexity to pack authors (must choose sync or async)
- Testing becomes more complex (mocking async, event loop fixtures)

### 2. Registry Async API

**What it was**: Async methods on `ResourceRegistry`:
- `async def aget_resource(name: str) -> ResourceContent`
- `async def asearch_resources(...) -> AsyncIterator[ResourceInfo]`
- `async def alist_resources(...) -> AsyncIterator[ResourceInfo]`

**Why removed**:
- Duplicates the API surface (sync + async versions of everything)
- Requires bridging logic (sync call on async pack, async call on sync pack)
- Adds maintenance burden (two code paths for every operation)

### 3. Sync↔Async Bridging

**What it was**: Automatic runtime detection and bridging:
- Sync call on async pack: `asyncio.run(pack.get_resource(name))` (creates event loop)
- Async call on sync pack: `loop.run_in_executor(None, pack.get_resource, name)` (thread pool)

**Why removed**:
- Event loop creation in sync contexts can cause conflicts (nested loops, existing loops)
- Thread pool executor adds overhead and complexity
- Makes behavior less predictable (which path executes?)

### 4. HTTP Client Injection (Async-Focused)

**What it was**: Patterns for injecting `httpx.AsyncClient` into online packs for connection pooling, caching middleware, etc.

**Why removed**: 
- Async clients require async context (event loops, `async with`)
- Sync clients (`requests.Session`, `httpx.Client`) work fine for blocking I/O
- Connection pooling works the same in sync mode

## Pros and Cons of Staying Sync-Only

### Pros

1. **Simplicity**: Single mental model—everything is blocking. No async/await, no event loops, no bridging.
2. **Zero Dependencies**: Core library stays dependency-free. Packs bring their own HTTP libraries (`requests`, `httpx.Client`).
3. **Universal Compatibility**: Works in any Python environment:
   - CLI tools and scripts
   - Web frameworks (Flask, Django) via blocking I/O or thread pools
   - GUI applications
   - Jupyter notebooks
   - No "function coloring" concerns
4. **Easier Testing**: Mock HTTP calls with standard `unittest.mock`, no async fixtures needed.
5. **Predictable Behavior**: No hidden event loops, no thread pool surprises, no async context manager requirements.

### Cons

1. **Blocking in Web Servers**: In async web frameworks (FastAPI, aiohttp), blocking I/O can starve the event loop. **Mitigation**: Use thread pool executors at the application level.
2. **No Native Concurrency**: Can't easily fetch multiple resources concurrently without threads/processes. **Mitigation**: Application-level concurrency (thread pools, worker queues).
3. **Potential Latency**: Blocking I/O means one request at a time per pack. **Mitigation**: Connection pooling (automatic with `requests.Session`/`httpx.Client`) and application-level parallelization.

## Future Options (If/When Needed)

If async support becomes necessary, here are potential approaches:

### Option A: Add Async API Surface

**What it would look like**:
- Add `AsyncResourcePack` protocol alongside `ResourcePack`
- Add async methods to `ResourceRegistry`: `aget_resource()`, `asearch_resources()`, etc.
- Implement sync↔async bridging in the registry

**Complexity**:
- **High**: Duplicates API surface, requires bridging logic, event loop management
- **Where it lands**: Registry becomes more complex, pack authors must choose sync/async

**When to consider**: If a significant number of online packs need async, or if web framework integration becomes a primary use case.

### Option B: Keep Sync Core; Recommend External Concurrency

**What it would look like**:
- Registry stays sync-only
- Applications use thread pools or worker queues for concurrent resource fetching
- Example: `concurrent.futures.ThreadPoolExecutor` for parallel `get_resource()` calls

**Complexity**:
- **Low**: No changes to JustMyResource
- **Where it lands**: Application-level concurrency management

**When to consider**: If occasional concurrent fetching is needed but not worth async complexity.

### Option C: Internal Kernel Pattern (Chosen Strategy)

**Status**: Already implemented in current architecture.

This approach keeps a single sync library while ensuring the resolution engine is a pure, side-effect-free kernel that can be extracted and reused for async later without logic duplication.

**What it provides**:
- **Single library**: No dual-library maintenance burden
- **Pure kernel**: `_resolve_name()` is intentionally pure (no I/O, only reads in-memory state)
- **Future-proof**: When async is needed, extract kernel into `justmyresource.resolution` and reuse in both sync and async registries
- **No feature split**: Resolution logic improvements apply to both sync and async immediately

**Implementation**: See "Chosen Strategy: Internal Kernel" section above for details.

**When to extract**: Only when async support is actually needed. Until then, the kernel remains as a well-documented method in `ResourceRegistry`.

## When to Revisit

Consider revisiting async support if:

1. **First real online pack** reveals blocking I/O is a significant problem in practice
2. **Web framework integration** becomes a primary use case and blocking I/O causes issues
3. **Very large media resources** (video, high-res images) become common and streaming is required
4. **Concurrent fetching** becomes a frequent need that thread pools don't solve well

Until then, the sync-only architecture provides simplicity and broad compatibility.

## Appendix: Sketch of Async API (Not Current)

If async support were added, the registry API might look like:

```python
# Sync API (current)
content = registry.get_resource("lucide:lightbulb")

# Async API (hypothetical)
content = await registry.aget_resource("lucide:lightbulb")

# Sync↔Async bridging (hypothetical)
# Sync call on async pack: asyncio.run(pack.get_resource(name))
# Async call on sync pack: loop.run_in_executor(None, pack.get_resource, name)
```

**Note**: This is a sketch only. The current architecture does **not** include these APIs.
