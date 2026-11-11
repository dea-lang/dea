/*
 * SPDX-License-Identifier: MIT OR Apache-2.0
 * Copyright (c) 2026 gwz
 */

/**
 * Verify complete native diagnostic data and a completed failure prefix.
 *
 * @param result Public entropy outcome.
 * @param count Required completed prefix.
 * @param domain Required native error namespace.
 * @param code Required full native error value.
 */
func _probe_failure(result: EntropyResult, count: int, domain: int, code: long) {
    match (result) {
        EntropyFailed(done, error) => {
            let native = os::_os_error_to_rt(error);
            assert(done == count && native.kind == 0 && native.domain == domain && native.native_code == code,
                "entropy preserves partial progress, Other, domain, and full native code");
        }
        _ => { assert(false, "entropy failure variant"); }
    }
}

/**
 * Exercise valid and malformed private schemas plus observable range dispatch.
 */
func main() {
    let scenario = system::argv(1);
    let success = RtOsError(0, 0, 0 as long);
    let failure = RangeDiagnostic(2, 0, 1, 4294967297 as long);
    if (scenario == "native_negative") { _encode_entropy_result(RtIoResult(0, -1, success)); return; }
    if (scenario == "native_stopped") { _encode_entropy_result(RtIoResult(1, 0, success)); return; }
    if (scenario == "native_timeout") { _encode_entropy_result(RtIoResult(3, 0, success)); return; }
    if (scenario == "native_unknown") { _encode_entropy_result(RtIoResult(4, 0, success)); return; }
    if (scenario == "requested_negative") { _decode_entropy_result(bytes::RangeActionApplied(-1, null), -1); return; }
    if (scenario == "applied_negative") { _decode_entropy_result(bytes::RangeActionApplied(-1, null), 1); return; }
    if (scenario == "applied_short") { _decode_entropy_result(bytes::RangeActionApplied(1, null), 2); return; }
    if (scenario == "applied_large") { _decode_entropy_result(bytes::RangeActionApplied(3, null), 2); return; }
    if (scenario == "applied_value") { _decode_entropy_result(bytes::RangeActionApplied(1, 0 as long?), 1); return; }
    if (scenario == "stopped") { _decode_entropy_result(bytes::RangeActionStopped(0, failure), 1); return; }
    if (scenario == "failed_negative") { _decode_entropy_result(bytes::RangeActionFailed(-1, failure), 1); return; }
    if (scenario == "failed_large") { _decode_entropy_result(bytes::RangeActionFailed(2, failure), 1); return; }
    if (scenario == "failed_tag") {
        _decode_entropy_result(bytes::RangeActionFailed(0, RangeDiagnostic(3, 0, 1, 1 as long)), 1); return;
    }
    if (scenario == "failed_domain") {
        _decode_entropy_result(bytes::RangeActionFailed(0, RangeDiagnostic(2, 0, -1, 1 as long)), 1); return;
    }
    if (scenario == "runtime_code") {
        _decode_entropy_result(bytes::RangeActionFailed(0, RangeDiagnostic(2, 14, 0, 1 as long)), 1); return;
    }
    if (scenario == "empty" || scenario == "bad_range") {
        with (let buffer = bytes::create() => bytes::free(buffer)) {
            let start = 0;
            if (scenario == "bad_range") { start = 1; }
            match (fill(buffer, start, 0)) {
                EntropyFilled => {}
                _ => { assert(false, "empty entropy dispatch succeeds"); }
            }
        }
        return;
    }
    assert(scenario == "normal", "unknown entropy conversion scenario");
    for (let amount = 0; amount < 4; amount = amount + 1) {
        match (_decode_entropy_result(_encode_entropy_result(RtIoResult(0, amount, success)), amount)) {
            EntropyFilled => {}
            _ => { assert(false, "entropy complete success"); }
        }
    }
    let domains: os::ErrorDomain[4] = [os::Runtime, os::Errno, os::Win32, os::NtStatus];
    for (let index = 0; index < dea::len(domains); index = index + 1) {
        let native = os::_os_error_to_rt(os::OsError(os::Other, domains[index], 4294967297 as long));
        if (index == 0) { native.native_code = 0 as long; }
        for (let done = 0; done <= 3; done = done + 1) {
            _probe_failure(_decode_entropy_result(_encode_entropy_result(RtIoResult(2, done, native)), 3),
                done, native.domain, native.native_code);
        }
    }
    _probe_failure(_decode_entropy_result(bytes::RangeActionFailed(2,
        RangeDiagnostic(2, 999, 1, -4294967297 as long)), 3), 2, 1, -4294967297 as long);
    _probe_failure(_decode_entropy_result(bytes::RangeActionFailed(2,
        RangeDiagnostic(2, 0, 3, 3221225506 as long)), 3), 2, 3, 3221225506 as long);
    printl_s("entropy range conversions: PASS");
}
