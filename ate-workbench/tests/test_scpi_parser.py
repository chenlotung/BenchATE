import pytest
from app.protocol import scalar, boolean, power_meter_batch, UnexpectedResponse


@pytest.mark.parametrize("text,value", [("1.2E+2\r\n", 120), ("-.25", -.25), (":MEASURE:UPDATE 0.5", .5)])
def test_numeric_supported_formats(text, value):
    assert scalar(text) == value


@pytest.mark.parametrize("text", ["NaN", "inf", "9.9e37", "1,2", "12 V", "", "ON", "1.2E999"])
def test_invalid_and_overload_rejected(text):
    with pytest.raises(UnexpectedResponse):
        scalar(text)


@pytest.mark.parametrize("text", ["1,2,3,4,.75,50", "1;2;3;4;.75;50", ":FETCH V 1,I 2,W 3,VA 4,PF .75,FREQ 50"])
def test_power_meter_batch_header_and_separator(text):
    assert power_meter_batch(text) == [1, 2, 3, 4, .75, 50]


@pytest.mark.parametrize("text", ["1,2,3", "V 1,I 2,VA 3,W 4,PF .75,FREQ 50", "1,2,bad,4,.75,50"])
def test_batch_wrong_order_or_partial_rejected(text):
    with pytest.raises(UnexpectedResponse):
        power_meter_batch(text)


def test_boolean_rejects_unknown():
    assert boolean("OFF").value == "OFF"
    assert boolean("+1").value == "ON"
    with pytest.raises(UnexpectedResponse):
        boolean("RUNNING")
