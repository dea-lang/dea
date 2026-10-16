#!/bin/sh
# SPDX-License-Identifier: MIT OR Apache-2.0
# Copyright (c) 2026 gwz

# Reconstruct the final Phase 5 controls in an owned container and retain its logs.
set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "usage: $0 NEW_OUTPUT_DIRECTORY [REPETITIONS]" >&2
    exit 2
fi
output=$1
repetitions=${2:-7}
case "$repetitions" in
    ''|*[!0-9]*) echo 'repetitions must be a positive integer' >&2; exit 2 ;;
esac
if [ "$repetitions" -eq 0 ] || [ -e "$output" ]; then
    echo 'repetitions must be positive and the output directory must be new' >&2
    exit 2
fi
repo=$(git rev-parse --show-toplevel)
evidence=$(CDPATH= cd "$(dirname "$0")" && pwd)
image=sha256:adb4f708244090afbf15505657a918d0f43bf36ca7863cda773a8580a5da8cf8
for directory in compiler build/dea/include build/dea/interfaces; do
    test -d "$repo/l1/$directory"
done
docker image inspect "$image" >/dev/null
scratch=$(mktemp -d "${TMPDIR:-/tmp}/dea-phase5-replay.XXXXXX")
container=dea-phase5-replay-$$
container_created=0
cleanup() {
    if [ "$container_created" -eq 1 ]; then
        docker rm -f "$container" >/dev/null 2>&1 || :
    fi
    rm -rf "$scratch"
}
trap cleanup EXIT HUP INT TERM
mkdir -p "$scratch/source/l1" "$output"
output=$(CDPATH= cd "$output" && pwd)
cp -R "$repo/l1/compiler" "$scratch/source/l1/compiler"
git -C "$scratch/source" apply "$evidence/../measured-preparation.patch"
git -C "$scratch/source" apply "$evidence/measured-discovery.patch"
mkdir -p "$scratch/candidate/build/bin" "$scratch/baseline/build/bin"
cp -R "$scratch/source/l1/compiler" "$scratch/candidate/compiler"
git -C "$scratch/source" apply "$evidence/without-instrumentation.patch"
cp -R "$scratch/source/l1/compiler" "$scratch/baseline/compiler"
for variant in baseline candidate; do
    cp -R "$repo/l1/build/dea/include" "$scratch/$variant/build/include"
    cp -R "$repo/l1/build/dea/interfaces" "$scratch/$variant/build/interfaces"
done
docker image inspect "$image" >"$output/image.json"
docker create --name "$container" --user 0 --cpus 2 --memory 2g \
    --entrypoint /bin/sh "$image" -c 'while :; do sleep 60; done' >/dev/null
container_created=1
docker cp "$scratch/baseline" "$container:/work/baseline"
docker cp "$scratch/candidate" "$container:/work/candidate"
docker cp "$evidence/measure.py" "$container:/work/measure.py"
docker start "$container" >/dev/null
docker exec "$container" /bin/sh -c '
    /usr/bin/gcc --version
    /usr/bin/clang --version
    L0_CC=/usr/bin/gcc L0_CFLAGS="-DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256" \
        /opt/dea/bin/l0c-stage2 --build \
        --c-source /work/baseline/compiler/support/interface_fingerprint.c \
        --c-source /work/baseline/compiler/support/compiler_support.c \
        --c-source /work/baseline/compiler/support/preparation_support.c \
        --project-root /work/baseline/compiler/src \
        -o /work/baseline/build/bin/l1c.native l1c
' >"$output/baseline-build.log" 2>&1
docker exec "$container" /bin/sh -c \
    'apt-get update -qq && apt-get install -y -qq --no-install-recommends python3 && python3 --version' \
    >"$output/python-setup.log" 2>&1
docker exec "$container" /bin/sh -c '
    L0_CC=/usr/bin/gcc L0_CFLAGS="-DL0_RT_CHECK_BASIC -D_RT_QUARANTINE_MAX_COUNT=256" \
        /opt/dea/bin/l0c-stage2 --build \
        --c-source /work/candidate/compiler/support/interface_fingerprint.c \
        --c-source /work/candidate/compiler/support/compiler_support.c \
        --c-source /work/candidate/compiler/support/preparation_support.c \
        --project-root /work/candidate/compiler/src \
        -o /work/candidate/build/bin/l1c.native l1c
' >"$output/candidate-build.log" 2>&1
measure_rc=0
docker exec "$container" python3 /work/measure.py \
    --root /work/measurements-fixed \
    --baseline /work/baseline/build/bin/l1c.native \
    --candidate /work/candidate/build/bin/l1c.native \
    --home /work/candidate/compiler --build /work/candidate/build \
    --compiler /usr/bin/gcc --compiler /usr/bin/clang --repetitions "$repetitions" \
    >"$output/measure.log" 2>&1 || measure_rc=$?
docker cp "$container:/work/measurements-fixed" "$output/measurements"
exit "$measure_rc"
