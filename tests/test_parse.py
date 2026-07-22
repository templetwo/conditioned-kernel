from conditioned_kernel.return_path.parse import parse_candidate


def test_parse_clean_json():
    raw = '{"answer":"hi","evidence_used":["a"],"next_state":{}}'
    c = parse_candidate(raw, packet_id="pkt_1")
    assert c["parse_ok"] is True
    assert c["answer"] == "hi"
    assert c["evidence_used"] == ["a"]


def test_parse_fenced_json():
    raw = 'Here you go:\n```json\n{"answer":"ok","evidence_used":[],"next_state":{}}\n```\n'
    c = parse_candidate(raw, packet_id="pkt_1")
    assert c["parse_ok"] is True
    assert c["answer"] == "ok"


def test_parse_garbage():
    c = parse_candidate("not json at all", packet_id="pkt_1")
    assert c["parse_ok"] is False
    assert c["parse_error"]
