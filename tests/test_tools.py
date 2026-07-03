from zenith.tools import try_handle_locally


def test_calculator_handles_basic_expression():
    result = try_handle_locally("hesapla: 12*7")
    assert result == "Sonuc: 84"


def test_calculator_handles_calc_alias():
    result = try_handle_locally("calc: (2+3)*4")
    assert result == "Sonuc: 20"


def test_calculator_rejects_unsafe_expression():
    result = try_handle_locally("hesapla: __import__('os').system('echo hi')")
    assert result.startswith("Bu ifadeyi hesaplayamadim")


def test_non_tool_message_returns_none():
    assert try_handle_locally("bugün nasılsın?") is None


def test_time_query():
    result = try_handle_locally("saat kac")
    assert result.startswith("Su an:")
