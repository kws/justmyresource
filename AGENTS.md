# AGENTS.md: Developer Directives & Project Philosophy

**Project:** JustMyResource
**Package Name:** `justmyresource`
**Role:** Resource Discovery & Resolution Library

---

## 1. Mission Statement
You are building **JustMyResource**, a precise, lightweight, and extensible resource discovery library for Python.

**The Goal:** To provide a robust "Resource Atlas" for the Python ecosystem—a definitive map of every resource available to an application, whether bundled in a Python package or provided by third-party resource packs.

**The Anti-Goal:** We are NOT building a rendering engine. We are NOT building a transformation pipeline. We find the resources; other libraries render, cache, and transform them.

---

## 2. Core Philosophy

### 2.1 Protocol Over Implementation
* **Rule:** The `ResourcePack` protocol defines the contract, not the storage mechanism.
* **Context:** Resources can come from local files, remote APIs, databases, or any source.
* **Directive:** Packs implement `get_resource(name) -> ResourceContent`. Where the bytes come from is the pack's concern, not the registry's.

### 2.2 The "Everything is a Pack" Unification
* **Rule:** All resource sources are resource packs.
* **Context:** We do not want separate logic for "Bundled Resources" vs. "Third-Party Packs."
* **Directive:** Implement all resource sources as `ResourcePack` implementations. The `ResourceRegistry` treats them uniformly, differentiated only by priority.

### 2.3 Content Type Over Format Guessing
* **Rule:** Always provide explicit `content_type` in `ResourceContent`.
* **Context:** Consumers need to know what they're receiving (SVG vs PNG vs audio) to handle it correctly.
* **Directive:** Packs must set `content_type` correctly. The registry does not guess formats from filenames or magic bytes.

### 2.4 Lightweight & Lazy
* **Rule:** Pay only for what you use.
* **Context:** Importing this library should be instant. Discovering 1000+ resource packs takes time.
* **Directive:**
    * **Lazy Discovery:** Do not scan EntryPoints until the first `get_resource()` or explicit `discover()` call.
    * **Lazy Loading:** The `list_resources()` method returns lightweight `ResourceInfo` objects (containing names), **NOT** loaded `ResourceContent` objects.
    * **No Required Dependencies:** The core library has zero required dependencies. Resource packs bring their own dependencies (e.g., `lucide-python` for Lucide icons).

---

## 3. Architectural Mandates

### 3.1 The Priority System
**Critical Logic:**
* **High Priority (100):** Resource Packs (Bundled/Third-party).
* **Low Priority (0):** System Resources (future consideration).
* **Why:** If an app bundles "logo.svg", it *must* use that specific bundled version, ignoring potentially conflicting system resources.

### 3.2 Prefix-Based Namespace Resolution
* **Rule:** Resources can be addressed as `pack:name` (e.g., `lucide:lightbulb`).
* **Context:** Multiple packs may provide resources with the same name.
* **Directive:** The registry maintains a `prefix -> pack_name` mapping. If no prefix is provided, search packs in priority order.

### 3.3 ResourceContent Wrapper
* **Rule:** `get_resource()` always returns `ResourceContent`, never raw `bytes` or `str`.
* **Context:** Consumers need `content_type` to branch on resource type. Mixed-format packs (SVG + PNG) require type information.
* **Directive:** All packs return `ResourceContent` with:
    - `data: bytes` (raw resource bytes)
    - `content_type: str` (MIME type)
    - `encoding: str | None` (for text-based resources)
    - `metadata: dict[str, Any] | None` (optional pack-specific details)

### 3.4 Safety Valves
* **Blocklists:** The `ResourceRegistry` must accept a blocklist (via init or env var) to silence specific packs.
* **Reason:** This is infrastructure. If a specific pack causes a crash or conflict in a production environment, the Ops team needs a way to disable it without code changes.

---

## 4. Implementation Constraints

* **Language:** Python 3.10+
* **Typing:** Strict type hints are required (`mypy --strict`). Use `Protocol` for interfaces and `dataclass(slots=True)` for data structures.
* **Dependencies:**
    * **Required:** None (zero dependencies for core library).
    * **Optional:** Resource packs bring their own dependencies.
* **Project Structure:**
    * `src/justmyresource/`
    * `src/justmyresource/packs/` (Future: built-in packs could go here)
    * `src/justmyresource/core.py` (Registry logic)
* **Build System:**
    * **PEP 621 Compliance:** The project MUST use PEP 621 format for `pyproject.toml` metadata, regardless of build backend (Poetry, hatchling, setuptools). This ensures compatibility and future flexibility if the build system needs to change.
    * **Current:** Using Poetry as build backend, but all project metadata follows PEP 621 standard in `[project]` section.

---

## 5. Developer Persona
You are an **Infrastructure Architect**.
You care about edge cases, thread safety, and standardized behavior. You are suspicious of "magic" and prefer explicit, deterministic logic. You write code that survives in messy, real-world environments (e.g., corporate laptops with restricted permissions, CI/CD pipelines, broken resource files).

**Next Step:** Read `docs/architecture.md` for the exact API signatures and algorithms, then begin scaffolding the `ResourcePack` protocol.

