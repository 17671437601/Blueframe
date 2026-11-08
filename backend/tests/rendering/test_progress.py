from blueframe.rendering.progress import FfmpegProgressParser


def test_progress_parser_handles_partial_lines_and_end_marker() -> None:
    parser = FfmpegProgressParser(duration_ms=4000)
    assert parser.feed("out_time_ms=1000000\npro") == [25.0]
    assert parser.feed("gress=continue\nout_time_us=3000000\nprogress=end\n") == [75.0, 100.0]
