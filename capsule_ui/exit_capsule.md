# 📦 Dependency Exit Capsule

**Target Dependency:** `urllib3` v`1.24.1`  
**Proposed Replacement:** `httpx @ 0.27.0`

---

## 🔍 Verified Evidence (Observed via Static Analysis & Execution)

### 🛑 Risk Indicators
- Deprecation Warning: Old SSL/TLS handling pattern
- High Vulnerability: CVE-2021-33503 (ReDoS in URL parsing)
- Unmaintained major version

### 📍 Usage Locations
- `linkwatch/fetcher.py` (Line 14)
- `linkwatch/utils.py` (Line 42)

### 🧪 Test Execution Results
- **Baseline Tests (Original Code):** ✅ PASSED
- **Migrated Tests (With Replacement):** ✅ PASSED

### ⚠️ Compatibility Gaps Identified
- httpx handles timeout parameters as a Timeout object rather than individual floats

---

## 🤖 Gemma 4 Recommendations (Unverified AI Guidance)

### 🛠️ Migration Steps
1. Replace urllib3.PoolManager() with httpx.Client()
2. Update request syntax from http.request('GET', url) to client.get(url)
3. Replace custom exception handlers with httpx.HTTPError

### ❓ Open Concerns & Limitations
- Asynchronous requests need additional testing under heavy load
