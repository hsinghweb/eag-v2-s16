import argparse
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_DELAY_SECONDS = 6
MAX_RETRIES = 5


def _post_json(url: str, payload: dict, timeout: int = 180) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else {}


def _backoff_sleep(attempt: int, base: int = 6, cap: int = 90) -> None:
    delay = min(cap, base * (2 ** attempt))
    time.sleep(delay)


def _should_retry_http(exc: HTTPError, attempt: int) -> bool:
    if exc.code != 429:
        return False
    if attempt >= MAX_RETRIES - 1:
        return False
    _backoff_sleep(attempt)
    return True


def _should_retry_timeout(attempt: int) -> bool:
    if attempt >= MAX_RETRIES - 1:
        return False
    _backoff_sleep(attempt, base=5)
    return True


def _should_retry_url(attempt: int) -> bool:
    if attempt >= MAX_RETRIES - 1:
        return False
    _backoff_sleep(attempt, base=3)
    return True


def _try_solve(url: str, payload: dict, attempt: int) -> tuple[bool, dict]:
    try:
        return True, _post_json(url, payload)
    except HTTPError as exc:
        if _should_retry_http(exc, attempt):
            return False, {}
        detail = exc.read().decode("utf-8") if exc.fp else str(exc)
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except TimeoutError as exc:
        if _should_retry_timeout(attempt):
            return False, {}
        raise RuntimeError("Request timed out") from exc
    except URLError as exc:
        if _should_retry_url(attempt):
            return False, {}
        raise RuntimeError(f"Failed to reach API at {url}") from exc


def _solve_problem(number: int, base_url: str) -> dict:
    url = f"{base_url}/leetcode/solve"
    payload = {"number": number}
    for attempt in range(MAX_RETRIES):
        success, result = _try_solve(url, payload, attempt)
        if success:
            return result
    raise RuntimeError("Max retries exceeded")


def _cleanup_folder(output_dir: Path, folder: str) -> None:
    if not folder:
        return
    folder_path = output_dir / folder
    if not folder_path.exists():
        return
    for child in folder_path.iterdir():
        try:
            child.unlink()
        except Exception:
            pass
    try:
        folder_path.rmdir()
    except Exception:
        pass


def _handle_result(result: dict, number: int, output_dir: Path, root: Path) -> bool:
    problem_id = result.get("problem_id") or f"{number:04d}"
    solution = (result.get("solution") or "").strip()
    if not solution:
        print(f"  - No solution returned for #{number}. Skipping.")
        return False
    solution_path = output_dir / f"Solution_{problem_id}.py"
    solution_path.write_text(solution + "\n", encoding="utf-8")
    print(f"  - Wrote {solution_path.relative_to(root)}")
    _cleanup_folder(output_dir, result.get("folder"))
    return True


def _run_one(number: int, base_url: str, output_dir: Path, root: Path) -> bool:
    result = _solve_problem(number, base_url)
    return _handle_result(result, number, output_dir, root)


def _print_failed(failed: list[int]) -> None:
    if failed:
        failed_list = ", ".join(str(n) for n in failed)
        print(f"Failed problems: {failed_list}")
    else:
        print("Failed problems: none")


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve LeetCode problems by range.")
    parser.add_argument("start", type=int, help="Starting problem number (inclusive).")
    parser.add_argument("end", type=int, help="Ending problem number (inclusive).")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL.")
    parser.add_argument("--delay", type=int, default=DEFAULT_DELAY_SECONDS, help="Delay between requests in seconds.")
    args = parser.parse_args()

    if args.start <= 0 or args.end <= 0:
        raise SystemExit("Start/end must be positive integers.")
    if args.end < args.start:
        raise SystemExit("End must be greater than or equal to start.")

    root = Path(__file__).resolve().parent
    output_dir = root / "memory" / "coding_workspaces" / "leetcode"
    output_dir.mkdir(parents=True, exist_ok=True)

    total_start = time.perf_counter()
    failed = []
    for idx, number in enumerate(range(args.start, args.end + 1), start=1):
        print(f"[{idx}] Solving LeetCode #{number}...")
        start_time = time.perf_counter()
        try:
            _run_one(number, args.base_url, output_dir, root)
        except Exception as exc:
            print(f"  - Failed for #{number}: {exc}")
            failed.append(number)
        finally:
            elapsed = time.perf_counter() - start_time
            print(f"  - Time: {elapsed:.2f}s")

        if number != args.end:
            time.sleep(max(1, int(args.delay)))
    total_elapsed = time.perf_counter() - total_start
    print(f"Total time: {total_elapsed:.2f}s")
    _print_failed(failed)


if __name__ == "__main__":
    main()
