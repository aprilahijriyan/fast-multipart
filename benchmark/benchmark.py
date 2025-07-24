import asyncio
import io
import mimetypes
import time
from typing import Any, Awaitable, Callable, Optional, TypedDict, Union


def make_multipart_body(boundary, fields) -> bytes:
    # fields: list of (name, filename, content_type, value)
    lines: list[str] = []
    for name, filename, content_type, value in fields:
        lines.append(f"--{boundary}")
        disp = f'form-data; name="{name}"'
        if filename:
            disp += f'; filename="{filename}"'
        lines.append(f"Content-Disposition: {disp}")
        if content_type:
            lines.append(f"Content-Type: {content_type}")
        elif not content_type and filename:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            lines.append(f"Content-Type: {content_type}")
        lines.append("")
        # Pastikan value bertipe str
        if isinstance(value, bytes):
            value = value.decode()
        lines.append(value)
    lines.append(f"--{boundary}--")
    lines.append("")
    return "\r\n".join(lines).encode()


class Timer:
    def __init__(self):
        self._start = None
        self._end = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        self._start = time.perf_counter()
        self._end = None

    def stop(self):
        if self._start is not None:
            self._end = time.perf_counter()

    @property
    def elapsed(self):
        if self._start is None:
            return 0
        if self._end is not None:
            return self._end - self._start
        return time.perf_counter() - self._start


OnFeedCallback = Callable[[bytes], Awaitable[Any]]
OnFinishCallback = Callable[[], Awaitable[Any]]


def humanize_bytes(num: Union[int, float]) -> str:
    """
    Convert a byte value into a human-readable string (e.g., 1.2 MB).
    """
    current = float(num)
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if current < 1024.0:
            return f"{current:.1f} {unit}"
        current /= 1024.0
    return f"{current:.1f} PB"


class Summary(TypedDict):
    total: int
    avg: float
    avg_throughput: float
    throughputs: list[float]
    timings: list[float]


class Benchmark:
    num_iteration = 10
    delay_before_test = 1
    chunk_size = 4 * 1024  # 4kb

    def __init__(self, name: str, boundary: str, payload: bytes) -> None:
        self.name = name
        self.boundary = boundary
        self.payload = payload
        self.payload_size = len(payload)
        self.human_size = humanize_bytes(self.payload_size)
        self.content_type = f'multipart/form-data; boundary="{self.boundary}"'
        self.summaries: list[Summary] = []

    def get_reader(self):
        return io.BytesIO(self.payload).read

    def make_summary(self, timing: list[float]):
        avg_time = sum(timing) / len(timing)
        avg_throughput = self.payload_size / avg_time
        throughputs = list(map(lambda x: self.payload_size / x, timing))
        return Summary(
            total=len(timing),
            timings=timing,
            avg=avg_time,
            avg_throughput=avg_throughput,
            throughputs=throughputs,
        )

    async def run(
        self,
        module_name: str,
        module_init: Callable[
            ["Benchmark"],
            Optional[
                tuple[
                    OnFeedCallback,  # on_feed
                    OnFinishCallback,  # on_finish
                ]
            ],
        ],
    ):
        print(
            f"Running benchmark {self.name!r} module_name={module_name} payload_size={self.payload_size} total={self.num_iteration}"
        )
        timing: list[float] = []
        success_bench = True
        for i in range(self.num_iteration):
            n = i + 1
            await asyncio.sleep(self.delay_before_test)
            print(f"[{n}/{self.num_iteration}] starting...")
            with Timer() as t:
                callback = module_init(self)
                if not callback:
                    success_bench = False
                    print(f"unable to benchmark. module {module_name!r} not found?")
                    break
                on_feed, on_finish = callback
                read = self.get_reader()
                while True:
                    chunk = read(self.chunk_size)
                    if not chunk:
                        break
                    await on_feed(chunk)
                await on_finish()
            timing.append(t.elapsed)
        if success_bench:
            summary = self.make_summary(timing)
            self.summaries.append(summary)


def generate_small_payload():
    boundary = "----boundary-test"
    fields = [
        ("field1", None, None, "value1"),
        ("field2", None, None, "value2"),
        ("field3", None, None, "value3"),
        ("field4", None, None, "value4"),
        ("field5", None, None, "value5"),
    ]
    return boundary, make_multipart_body(boundary, fields)


def generate_medium_payload():
    boundary = "----boundary-test"
    file_content = b"x" * (4 * 1024 * 1024)  # 4MB
    fields = [
        ("field1", None, None, "value1"),
        ("field2", None, None, "value2"),
        ("field3", None, None, "value3"),
        ("field4", None, None, "value4"),
        ("field5", None, None, "value5"),
        ("file1", "file1.bin", "application/octet-stream", file_content),
        ("file2", "file2.bin", "application/octet-stream", file_content),
    ]
    return boundary, make_multipart_body(boundary, fields)


def generate_large_payload():
    boundary = "----boundary-test"
    file_content = b"x" * (40 * 1024 * 1024)  # 40MB
    fields = [
        ("file1", "file1.bin", "application/octet-stream", file_content),
        ("file2", "file2.bin", "application/octet-stream", file_content),
    ]
    return boundary, make_multipart_body(boundary, fields)

def generate_extra_large_payload():
    boundary = "----boundary-test"
    file_content = b"x" * (100 * 1024 * 1024)  # 100MB
    fields = [
        ("file1", "file1.bin", "application/octet-stream", file_content),
        ("file2", "file2.bin", "application/octet-stream", file_content),
    ]
    return boundary, make_multipart_body(boundary, fields)

def generate_2xl_payload():
    boundary = "----boundary-test"
    file_content = b"x" * (500 * 1024 * 1024)  # 100MB
    fields = [
        ("file1", "file1.bin", "application/octet-stream", file_content),
        ("file2", "file2.bin", "application/octet-stream", file_content),
    ]
    return boundary, make_multipart_body(boundary, fields)

def fast_multipart_init(self: Benchmark):
    try:
        from fast_multipart import MultipartParser
    except ImportError:
        return

    def on_field(*args):
        pass

    def on_field_data(*args):
        pass

    def on_field_end():
        pass

    parser = MultipartParser(
        self.boundary,
        on_field=on_field,
        on_field_data=on_field_data,
        on_field_end=on_field_end,
    )

    async def on_feed(data: bytes):
        parser.feed(
            data,
        )

    async def on_finish():
        parser.close()

    return on_feed, on_finish

def multipart_init(self: Benchmark):
    try:
        import multipart
    except ImportError:
        return

    mps = multipart.MultipartSegment
    parser = multipart.PushMultipartParser(self.boundary)

    async def on_feed(data: bytes):
        for event in parser.parse(data):
            if isinstance(event, mps):
                pass
            elif event:
                pass
            else:
                pass

    async def on_finish():
        parser.close()

    return on_feed, on_finish


MODULES = [
    ("fast-multipart", fast_multipart_init),
    ("multipart", multipart_init),
]

MODULE_SUMMARIES: list[tuple[str, str, dict[str, list[Summary]]]] = []

async def run_benchmark(bench: Benchmark):
    summaries: dict[str, list[Summary]] = {}
    for name, init in MODULES:
        await bench.run(name, init)
        summaries[name] = bench.summaries.copy()
        bench.summaries = []

    MODULE_SUMMARIES.append((bench.name, bench.human_size, summaries))

def format_summary(name: str, s: Summary):
    throughputs = s["throughputs"]
    timings = s["timings"]
    min_tp = min(throughputs)
    max_tp = max(throughputs)
    avg_tp = s["avg_throughput"]
    min_time = min(timings)
    max_time = max(timings)
    avg_time = s["avg"]
    print(f"\n📊 Benchmark Summary ({name}):")
    print(f"  🔢 Total Iterations: {s['total']}")
    print("  ⏱️  Time (seconds):")
    print(f"    • Min:  {min_time:.4f} s 🏎️")
    print(f"    • Avg:  {avg_time:.4f} s ⚡")
    print(f"    • Max:  {max_time:.4f} s 🐢")
    print("  🚀 Throughput:")
    print(f"    • Min:  {humanize_bytes(min_tp)}/s 🐢")
    print(f"    • Avg:  {humanize_bytes(avg_tp)}/s ⚡")
    print(f"    • Max:  {humanize_bytes(max_tp)}/s 🏎️")

def print_summary():
    for bench_name, payload_size, bench_data in MODULE_SUMMARIES:
        for mod_name, list_sm in bench_data.items():
            if len(list_sm) == 0:
                print(
                    f"unable to display summary, module {mod_name!r} failed during benchmarking."
                )
                continue
            for sm in list_sm:
                format_summary(f"{mod_name} - {bench_name} {payload_size}", sm)


async def main():
    # Small payload
    boundary, payload = generate_small_payload()
    bench = Benchmark("sm", boundary, payload)
    await run_benchmark(bench)

    # Medium payload
    boundary, payload = generate_medium_payload()
    bench = Benchmark("md", boundary, payload)
    await run_benchmark(bench)

    # Large payload
    boundary, payload = generate_large_payload()
    bench = Benchmark("lg", boundary, payload)
    await run_benchmark(bench)

    # Extra Large payload
    boundary, payload = generate_extra_large_payload()
    bench = Benchmark("xl", boundary, payload)
    await run_benchmark(bench)

    # 2xl payload
    boundary, payload = generate_2xl_payload()
    bench = Benchmark("2xl", boundary, payload)
    await run_benchmark(bench)

    print_summary()

if __name__ == "__main__":
    asyncio.run(main())
