# L0/L1 Compiler Performance Assessment

- Assessment date: 2026-07-15
- Status: Point-in-time evidence
- Related plan:
  [work/plans/features/closed/2026-07-16-shared-compiler-runtime-check-basic-default-noref.md](../closed/2026-07-16-shared-compiler-runtime-check-basic-default-noref.md)

This report records a warm-cache, single-host assessment used to choose the runtime defaults for native L0 Stage 2 and
L1 Stage 1 compiler binaries. It is historical evidence rather than a maintained performance specification.

## Snapshot Legend

The assessment identifies repository states with descriptive monikers:

| Moniker                                         | Meaning                                                                    |
| ----------------------------------------------- | -------------------------------------------------------------------------- |
| 1.1.0 release baseline                          | The released compiler and source baseline before pointer-access validation |
| pre-pointer-validation snapshot                 | The immediate predecessor of the pointer-validation implementation         |
| pointer-validation introduction                 | The first snapshot containing runtime pointer-access validation            |
| post-allocation-record-optimization snapshot    | The selected checkpoint after allocation-record optimization               |
| checked-runtime modes and provenance completion | The checkpoint completing checked-runtime modes and provenance             |
| 2026-07-15 assessment snapshot                  | The repository state measured at the end of the historical series          |

The intermediate matrix uses the fixed hashmap workload. The 1.1.0 release baseline and 2026-07-15 assessment snapshot
also use hello and hamurabi. Full and basic suffixes name the runtime mode of the compiler executable itself. No timed
command selected basic mode for the program being compiled.

## Executive Assessment

The compile-time regression is real and large, but the sampled history localizes it to the pointer-validation
introduction, not to checked-runtime modes and provenance completion. On the fixed 1,037-line hashmap workload,
pointer-validation introduction versus the pre-pointer-validation snapshot raises compiler-only `--gen` wall time by
**4.482x for L0** and **4.983x for L1**; end-to-end `--build` rises by **1.604x for L0** and **2.373x for L1**. Every
corresponding total-CPU interval confirms the increase.

The full checked-runtime modes and provenance completion snapshot is effectively flat against the
post-allocation-record-optimization snapshot. The sole interval narrowly excluding no change is L1 `--gen` total CPU at
+2.0%; wall time, build time, and the L0 results do not corroborate a material boundary regression. The 2026-07-15
assessment snapshot is also flat against checked-runtime modes and provenance completion in matching modes.

Basic checked mode recovers part of the cost. At the assessment snapshot it reduces `--gen` wall time by 16 to 18% for
L0 and 21 to 25% for L1 versus full mode. End-to-end build improvements are smaller: about 5% for L0 and 9 to 15% for
L1. It does not restore 1.1.0 performance: assessment-snapshot basic `--gen` remains 3.65 to 4.10x baseline for L0 and
3.95 to 4.25x for L1.

## Representative Hashmap Medians

Values are median wall / total child CPU seconds. Delta cells are wall / total CPU percentage changes with 95% bootstrap
intervals.

| Compiler   | Operation | 1.1.0 baseline | Assessment full | Full vs baseline                                        | Assessment basic | Basic vs baseline                                       | Basic vs full                                     |
| ---------- | --------- | -------------: | --------------: | ------------------------------------------------------- | ---------------: | ------------------------------------------------------- | ------------------------------------------------- |
| L0 Stage 2 | `--build` |  0.933 / 0.956 |   1.522 / 1.537 | +63.1% [+57.3%, +70.4%] / +60.8% [+56.9%, +66.0%]       |    1.451 / 1.466 | +55.5% [+50.3%, +64.3%] / +53.4% [+49.9%, +59.1%]       | -4.7% [-8.4%, +0.7%] / -4.6% [-7.7%, -0.9%]       |
| L0 Stage 2 | `--gen`   |  0.103 / 0.090 |   0.468 / 0.452 | +356.8% [+339.8%, +376.8%] / +400.6% [+383.9%, +417.9%] |    0.382 / 0.365 | +272.6% [+258.5%, +287.0%] / +304.5% [+291.9%, +319.6%] | -18.4% [-21.7%, -15.5%] / -19.2% [-21.6%, -16.3%] |
| L1 Stage 1 | `--build` |  0.661 / 0.696 |   1.564 / 1.589 | +136.4% [+128.3%, +145.4%] / +128.3% [+122.0%, +135.3%] |    1.419 / 1.445 | +114.6% [+106.5%, +123.5%] / +107.6% [+101.2%, +114.8%] | -9.2% [-12.3%, -6.1%] / -9.1% [-11.8%, -6.3%]     |
| L1 Stage 1 | `--gen`   |  0.132 / 0.119 |   0.658 / 0.640 | +399.1% [+379.5%, +416.3%] / +439.3% [+429.5%, +454.4%] |    0.521 / 0.500 | +294.9% [+275.3%, +314.9%] / +321.1% [+307.3%, +335.8%] | -20.9% [-24.2%, -17.2%] / -21.9% [-24.7%, -19.4%] |

The `--gen`/`--build` gap is important: Clang compilation and linking add a large downstream component that dilutes the
compiler-runtime regression. L1 still exceeds 2x baseline on hashmap builds because its compiler-only increase is so
large.

## Primary Workload Comparisons

Ratios are candidate/reference. CPU means total child user + system CPU. Intervals are fixed-seed, 10,000-resample
bootstrap 95% confidence intervals.

### Assessment Snapshot Full Versus 1.1.0

| Compiler / workload |                            Build wall |                             Build CPU |                              Gen wall |                               Gen CPU |
| ------------------- | ------------------------------------: | ------------------------------------: | ------------------------------------: | ------------------------------------: |
| L0 `hello`          |  1.590x (+59.0%; 95% CI 1.528-1.641x) |  1.562x (+56.2%; 95% CI 1.511-1.597x) | 4.349x (+334.9%; 95% CI 4.166-4.505x) | 4.804x (+380.4%; 95% CI 4.610-4.968x) |
| L0 `hamurabi`       |  1.719x (+71.9%; 95% CI 1.682-1.767x) |  1.686x (+68.6%; 95% CI 1.657-1.719x) | 4.997x (+399.7%; 95% CI 4.786-5.135x) | 5.308x (+430.8%; 95% CI 5.158-5.447x) |
| L0 `hashmap_bench`  |  1.631x (+63.1%; 95% CI 1.573-1.704x) |  1.608x (+60.8%; 95% CI 1.569-1.660x) | 4.568x (+356.8%; 95% CI 4.398-4.768x) | 5.006x (+400.6%; 95% CI 4.839-5.179x) |
| L1 `hello`          | 2.180x (+118.0%; 95% CI 2.081-2.301x) | 2.104x (+110.4%; 95% CI 2.054-2.203x) | 5.382x (+438.2%; 95% CI 5.167-5.549x) | 5.562x (+456.2%; 95% CI 5.420-5.720x) |
| L1 `hamurabi`       | 2.263x (+126.3%; 95% CI 2.166-2.405x) | 2.224x (+122.4%; 95% CI 2.130-2.322x) | 5.673x (+467.3%; 95% CI 5.321-6.100x) | 5.810x (+481.0%; 95% CI 5.547-6.033x) |
| L1 `hashmap_bench`  | 2.364x (+136.4%; 95% CI 2.283-2.454x) | 2.283x (+128.3%; 95% CI 2.220-2.353x) | 4.991x (+399.1%; 95% CI 4.795-5.163x) | 5.393x (+439.3%; 95% CI 5.295-5.544x) |

### Assessment Snapshot Basic Versus 1.1.0

| Compiler / workload |                            Build wall |                             Build CPU |                              Gen wall |                               Gen CPU |
| ------------------- | ------------------------------------: | ------------------------------------: | ------------------------------------: | ------------------------------------: |
| L0 `hello`          |  1.504x (+50.4%; 95% CI 1.447-1.569x) |  1.483x (+48.3%; 95% CI 1.435-1.528x) | 3.649x (+264.9%; 95% CI 3.489-3.768x) | 4.036x (+303.6%; 95% CI 3.854-4.111x) |
| L0 `hamurabi`       |  1.636x (+63.6%; 95% CI 1.580-1.677x) |  1.598x (+59.8%; 95% CI 1.559-1.625x) | 4.098x (+309.8%; 95% CI 3.931-4.242x) | 4.341x (+334.1%; 95% CI 4.232-4.492x) |
| L0 `hashmap_bench`  |  1.555x (+55.5%; 95% CI 1.503-1.643x) |  1.534x (+53.4%; 95% CI 1.499-1.591x) | 3.726x (+272.6%; 95% CI 3.585-3.870x) | 4.045x (+304.5%; 95% CI 3.919-4.196x) |
| L1 `hello`          |  1.850x (+85.0%; 95% CI 1.798-1.968x) |  1.811x (+81.1%; 95% CI 1.773-1.895x) | 4.085x (+308.5%; 95% CI 3.939-4.224x) | 4.219x (+321.9%; 95% CI 4.128-4.337x) |
| L1 `hamurabi`       |  1.944x (+94.4%; 95% CI 1.884-2.015x) |  1.916x (+91.6%; 95% CI 1.862-1.980x) | 4.250x (+325.0%; 95% CI 4.002-4.407x) | 4.383x (+338.3%; 95% CI 4.189-4.488x) |
| L1 `hashmap_bench`  | 2.146x (+114.6%; 95% CI 2.065-2.235x) | 2.076x (+107.6%; 95% CI 2.012-2.148x) | 3.949x (+294.9%; 95% CI 3.753-4.149x) | 4.211x (+321.1%; 95% CI 4.073-4.358x) |

### Assessment Snapshot Basic Versus Full

| Compiler / workload |                           Build wall |                            Build CPU |                             Gen wall |                              Gen CPU |
| ------------------- | -----------------------------------: | -----------------------------------: | -----------------------------------: | -----------------------------------: |
| L0 `hello`          |  0.946x (-5.4%; 95% CI 0.917-0.980x) |  0.949x (-5.1%; 95% CI 0.928-0.975x) | 0.839x (-16.1%; 95% CI 0.810-0.867x) | 0.840x (-16.0%; 95% CI 0.806-0.858x) |
| L0 `hamurabi`       |  0.952x (-4.8%; 95% CI 0.918-0.974x) |  0.948x (-5.2%; 95% CI 0.923-0.963x) | 0.820x (-18.0%; 95% CI 0.796-0.851x) | 0.818x (-18.2%; 95% CI 0.799-0.845x) |
| L0 `hashmap_bench`  |  0.953x (-4.7%; 95% CI 0.916-1.007x) |  0.954x (-4.6%; 95% CI 0.923-0.991x) | 0.816x (-18.4%; 95% CI 0.783-0.845x) | 0.808x (-19.2%; 95% CI 0.784-0.837x) |
| L1 `hello`          | 0.848x (-15.2%; 95% CI 0.804-0.914x) | 0.861x (-13.9%; 95% CI 0.824-0.903x) | 0.759x (-24.1%; 95% CI 0.737-0.790x) | 0.759x (-24.1%; 95% CI 0.740-0.781x) |
| L1 `hamurabi`       | 0.859x (-14.1%; 95% CI 0.811-0.900x) | 0.861x (-13.9%; 95% CI 0.832-0.898x) | 0.749x (-25.1%; 95% CI 0.695-0.780x) | 0.754x (-24.6%; 95% CI 0.726-0.774x) |
| L1 `hashmap_bench`  |  0.908x (-9.2%; 95% CI 0.877-0.939x) |  0.909x (-9.1%; 95% CI 0.882-0.937x) | 0.791x (-20.9%; 95% CI 0.758-0.828x) | 0.781x (-21.9%; 95% CI 0.753-0.806x) |

The only assessment-snapshot basic/full wall interval crossing 1.0 is L0 hashmap `--build`; its total-CPU result still
favors basic mode. Every `--gen` mode comparison is decisive.

## Historical Localization on Hashmap

### L0 Stage 2

| Boundary                                                                                    |                           Build wall |                            Build CPU |                              Gen wall |                               Gen CPU |
| ------------------------------------------------------------------------------------------- | -----------------------------------: | -----------------------------------: | ------------------------------------: | ------------------------------------: |
| Pointer-validation introduction vs pre-pointer-validation snapshot                          | 1.604x (+60.4%; 95% CI 1.540-1.724x) | 1.575x (+57.5%; 95% CI 1.527-1.649x) | 4.482x (+348.2%; 95% CI 4.205-4.716x) | 5.088x (+408.8%; 95% CI 4.826-5.211x) |
| Post-allocation-record-optimization vs pointer-validation introduction                      |  1.008x (+0.8%; 95% CI 0.935-1.046x) |  1.006x (+0.6%; 95% CI 0.962-1.033x) |   1.002x (+0.2%; 95% CI 0.981-1.040x) |   0.989x (-1.1%; 95% CI 0.973-1.027x) |
| Checked-runtime modes and provenance completion full vs post-allocation-record-optimization |  1.009x (+0.9%; 95% CI 0.981-1.037x) |  1.009x (+0.9%; 95% CI 0.993-1.027x) |   0.983x (-1.7%; 95% CI 0.956-1.017x) |   0.999x (-0.1%; 95% CI 0.965-1.012x) |
| Assessment snapshot full vs checked-runtime modes and provenance completion full            |  1.000x (-0.0%; 95% CI 0.965-1.039x) |  0.996x (-0.4%; 95% CI 0.976-1.028x) |   1.007x (+0.7%; 95% CI 0.967-1.045x) |   1.003x (+0.3%; 95% CI 0.977-1.040x) |
| Checked-runtime modes and provenance completion basic vs full                               |  0.933x (-6.7%; 95% CI 0.910-0.959x) |  0.934x (-6.6%; 95% CI 0.919-0.952x) |  0.826x (-17.4%; 95% CI 0.794-0.848x) |  0.808x (-19.2%; 95% CI 0.794-0.837x) |

### L1 Stage 1

| Boundary                                                                                    |                            Build wall |                             Build CPU |                              Gen wall |                               Gen CPU |
| ------------------------------------------------------------------------------------------- | ------------------------------------: | ------------------------------------: | ------------------------------------: | ------------------------------------: |
| Pointer-validation introduction vs pre-pointer-validation snapshot                          | 2.373x (+137.3%; 95% CI 2.293-2.481x) | 2.299x (+129.9%; 95% CI 2.223-2.368x) | 4.983x (+398.3%; 95% CI 4.808-5.206x) | 5.394x (+439.4%; 95% CI 5.272-5.543x) |
| Post-allocation-record-optimization vs pointer-validation introduction                      |   0.996x (-0.4%; 95% CI 0.954-1.061x) |   0.997x (-0.3%; 95% CI 0.964-1.046x) |   0.982x (-1.8%; 95% CI 0.936-1.016x) |   0.985x (-1.5%; 95% CI 0.948-1.001x) |
| Checked-runtime modes and provenance completion full vs post-allocation-record-optimization |   1.007x (+0.7%; 95% CI 0.946-1.062x) |   1.003x (+0.3%; 95% CI 0.959-1.028x) |   1.019x (+1.9%; 95% CI 0.991-1.106x) |   1.020x (+2.0%; 95% CI 1.001-1.081x) |
| Assessment snapshot full vs checked-runtime modes and provenance completion full            |   0.990x (-1.0%; 95% CI 0.937-1.017x) |   0.991x (-0.9%; 95% CI 0.974-1.017x) |   0.985x (-1.5%; 95% CI 0.914-1.015x) |   0.991x (-0.9%; 95% CI 0.940-1.017x) |
| Checked-runtime modes and provenance completion basic vs full                               |   0.908x (-9.2%; 95% CI 0.861-0.931x) |   0.909x (-9.1%; 95% CI 0.890-0.929x) |  0.768x (-23.2%; 95% CI 0.705-0.788x) |  0.762x (-23.8%; 95% CI 0.718-0.780x) |

The history is a step function: the large increase appears at pointer-validation introduction; the
post-allocation-record-optimization snapshot, checked-runtime modes and provenance completion full, and the assessment
snapshot full form a performance plateau within these intervals. The small L1 checked-runtime modes and provenance
completion `--gen` total-CPU increase (+2.0%, CI +0.1% to +8.1%) is not matched by wall time or builds and is tiny
beside the 5.394x CPU ratio at pointer-validation introduction.

## Python Stage 1 Contextual Control

The same Python 3.14.5 interpreter ran the 1.1.0 release baseline and 2026-07-15 assessment snapshot. This is contextual
rather than purely causal because backend output and the matching output runtime changed.

| Workload        |                           Build wall |                            Build CPU |                            Gen wall |                             Gen CPU |
| --------------- | -----------------------------------: | -----------------------------------: | ----------------------------------: | ----------------------------------: |
| `hello`         | 1.163x (+16.3%; 95% CI 1.095-1.207x) | 1.156x (+15.6%; 95% CI 1.132-1.190x) | 0.996x (-0.4%; 95% CI 0.959-1.038x) | 1.000x (+0.0%; 95% CI 0.975-1.035x) |
| `hamurabi`      | 1.172x (+17.2%; 95% CI 1.131-1.208x) | 1.170x (+17.0%; 95% CI 1.133-1.192x) | 0.996x (-0.4%; 95% CI 0.944-1.032x) | 0.998x (-0.2%; 95% CI 0.969-1.024x) |
| `hashmap_bench` | 1.179x (+17.9%; 95% CI 1.137-1.241x) | 1.173x (+17.3%; 95% CI 1.149-1.223x) | 1.051x (+5.1%; 95% CI 1.012-1.086x) | 1.034x (+3.4%; 95% CI 1.010-1.066x) |

Python `--gen` is flat for hello and hamurabi and only modestly higher for hashmap (+5.1% wall, +3.4% CPU). Python
`--build` rises 16 to 18%, consistent with downstream generated-C/runtime/Clang changes. That is far smaller than the
native full compiler's roughly 4.5 to 5.7x `--gen` wall ratios, supporting compiler-runtime validation as the dominant
cause.

## Methodology and Validation

- Host: MacBookPro16,1, Intel Core i7 2.6 GHz, 6 physical / 12 logical cores, 32 GB RAM, macOS 15.7.7 (24G720), x86_64.
- C compiler: `/usr/bin/clang`, Apple Clang 17.0.0 (`clang-1700.6.4.2`). Build workloads used
  `--c-options='-O1 -Wno-c23-extensions'`.
- Compiler builds were `-O2`. Checked compiler runtimes used quarantine record limit 256. Basic L0 compilers used
  `L0_RT_CHECK_BASIC=1`; basic L1 compilers used `L0_CFLAGS='-O2 -Wno-c23-extensions -DL0_RT_CHECK_BASIC'`.
- Sources and `-S` sysroots were fixed at the 1.1.0 release baseline. Build cells used each snapshot's compatible
  default/full output runtime ABI; basic compiler cells deliberately shared the same-snapshot full output runtime. No
  timed command passed `--check-basic`.
- An initial untimed preflight that forced the 1.1.0 output runtime onto newer generated C failed on the
  pointer-validation ABI (`_rt_ptr_site` and related symbols). The corrected snapshot-compatible runtime mapping passed
  before timing; the failed setup contributed no timed sample.
- Workloads were the 1.1.0 `hello` and `hamurabi` examples plus a 41-line L0/L1 driver importing the 1,037-line
  `std.hashmap` module. The L0 and L1 hashmap sources and drivers were verified byte-identical.
- Collection used two untimed warmup blocks followed by 30 measured randomized blocks with seed 20,260,715. The 68 cases
  ran sequentially in every block with unique outputs.
- Timing used `perf_counter_ns()` wall time and before/after `getrusage(RUSAGE_CHILDREN)` child-tree user/system CPU.
  All 2,040 measured samples succeeded and were retained; no outlier filtering was applied.
- Statistics use R-7 quartiles and p95. Ratio and percentage intervals use 10,000 independent percentile-bootstrap
  resamples with seed 20,260,715. CPU comparisons use total child user + system CPU; user and system components are
  reported separately below.
- Validation passed 68/68 preflight compiles, 26/26 hello/hashmap executable smoke tests, and 8/8 full/basic generated-C
  identity pairs byte-for-byte. Compiler provenance and version output were checked against each named snapshot before
  timing.
- Apple Clang 17 diagnoses a historical anonymous-struct `offsetof` C23 extension under `-pedantic-errors`. The uniform
  `-Wno-c23-extensions` compatibility flag suppressed that diagnostic only.
- Interpretation is warm-cache, single-host performance. Absolute L0 and L1 times are not treated as equivalent
  workloads.

## Complete Descriptive Statistics

All values are seconds. Each metric reports median / IQR / p95; `n=30` for every cell.

| Case                                                                                           |           Wall med/IQR/p95 |       User CPU med/IQR/p95 |     System CPU med/IQR/p95 |      Total CPU med/IQR/p95 |
| ---------------------------------------------------------------------------------------------- | -------------------------: | -------------------------: | -------------------------: | -------------------------: |
| `L0 Stage 2 / 1.1.0 release baseline / hello / --build`                                        | 0.781688/0.066869/0.969629 | 0.719780/0.037506/0.824383 | 0.094326/0.016531/0.124810 | 0.814761/0.059207/0.948975 |
| `L0 Stage 2 / 1.1.0 release baseline / hello / --gen`                                          | 0.083831/0.009481/0.099532 | 0.062214/0.003278/0.067757 | 0.009743/0.002171/0.014048 | 0.071769/0.005727/0.080728 |
| `L0 Stage 2 / 1.1.0 release baseline / hamurabi / --build`                                     | 1.232059/0.069741/1.390308 | 1.161436/0.037528/1.269832 | 0.100170/0.009521/0.122588 | 1.261644/0.050762/1.389111 |
| `L0 Stage 2 / 1.1.0 release baseline / hamurabi / --gen`                                       | 0.141465/0.012885/0.182950 | 0.117062/0.007205/0.131270 | 0.011813/0.002291/0.018110 | 0.129447/0.008833/0.149387 |
| `L0 Stage 2 / 1.1.0 release baseline / hashmap_bench / --build`                                | 0.933184/0.078505/1.101652 | 0.857726/0.033838/0.944259 | 0.097407/0.013903/0.115778 | 0.955512/0.048114/1.057725 |
| `L0 Stage 2 / 1.1.0 release baseline / hashmap_bench / --gen`                                  | 0.102532/0.008453/0.132354 | 0.079594/0.004124/0.092468 | 0.010422/0.002061/0.017260 | 0.090195/0.005770/0.110400 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot full / hello / --build`                           | 1.243024/0.093561/1.485285 | 1.165044/0.053068/1.263569 | 0.105976/0.016804/0.129333 | 1.272805/0.072244/1.387709 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot full / hello / --gen`                             | 0.364561/0.027769/0.478219 | 0.329173/0.017354/0.381644 | 0.016661/0.004312/0.021790 | 0.344804/0.021888/0.402957 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot full / hamurabi / --build`                        | 2.117560/0.130925/2.434056 | 2.005268/0.113227/2.205625 | 0.125851/0.026827/0.166510 | 2.126662/0.111318/2.369881 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot full / hamurabi / --gen`                          | 0.706892/0.052894/0.791830 | 0.667027/0.031013/0.723118 | 0.021187/0.006641/0.032326 | 0.687078/0.036230/0.753747 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot full / hashmap_bench / --build`                   | 1.522091/0.137150/1.831803 | 1.428189/0.078060/1.662048 | 0.112536/0.018549/0.149149 | 1.536810/0.095154/1.811015 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot full / hashmap_bench / --gen`                     | 0.468333/0.040886/0.581778 | 0.434103/0.026309/0.508357 | 0.017441/0.005293/0.028493 | 0.451507/0.030926/0.536543 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot basic / hello / --build`                          | 1.175767/0.127240/1.329232 | 1.105526/0.080415/1.194367 | 0.103103/0.016368/0.128820 | 1.208420/0.101769/1.313245 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot basic / hello / --gen`                            | 0.305892/0.030589/0.344192 | 0.271717/0.015569/0.298996 | 0.015799/0.005097/0.020135 | 0.289650/0.017528/0.318885 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot basic / hamurabi / --build`                       | 2.016081/0.120904/2.521945 | 1.891916/0.066759/2.049044 | 0.123230/0.016920/0.183397 | 2.016311/0.094199/2.237102 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot basic / hamurabi / --gen`                         | 0.579664/0.049009/0.721633 | 0.541444/0.033015/0.614000 | 0.020988/0.006576/0.032467 | 0.561896/0.038513/0.646467 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot basic / hashmap_bench / --build`                  | 1.450728/0.146736/1.874218 | 1.353951/0.076829/1.567279 | 0.111470/0.023796/0.179404 | 1.466130/0.106793/1.748456 |
| `L0 Stage 2 / 2026-07-15 assessment snapshot basic / hashmap_bench / --gen`                    | 0.382030/0.027914/0.527756 | 0.349013/0.021812/0.416421 | 0.015667/0.004623/0.031804 | 0.364833/0.024310/0.447228 |
| `L0 Stage 2 / pre-pointer-validation snapshot / hashmap_bench / --build`                       | 0.933413/0.069671/1.211318 | 0.864481/0.045992/0.982954 | 0.099894/0.013519/0.132542 | 0.964623/0.062699/1.119797 |
| `L0 Stage 2 / pre-pointer-validation snapshot / hashmap_bench / --gen`                         | 0.105411/0.017408/0.146560 | 0.078345/0.008133/0.097402 | 0.011369/0.002631/0.017898 | 0.089500/0.010582/0.115692 |
| `L0 Stage 2 / pointer-validation introduction full / hashmap_bench / --build`                  | 1.497444/0.215442/1.917216 | 1.413969/0.118121/1.604208 | 0.108234/0.031569/0.162665 | 1.519480/0.156467/1.762806 |
| `L0 Stage 2 / pointer-validation introduction full / hashmap_bench / --gen`                    | 0.472460/0.047799/0.558875 | 0.438251/0.029499/0.480966 | 0.016453/0.006359/0.026103 | 0.455355/0.038671/0.504588 |
| `L0 Stage 2 / post-allocation-record-optimization snapshot full / hashmap_bench / --build`     | 1.509814/0.142405/2.057028 | 1.417626/0.079494/1.682434 | 0.109009/0.016073/0.166771 | 1.529255/0.096864/1.853338 |
| `L0 Stage 2 / post-allocation-record-optimization snapshot full / hashmap_bench / --gen`       | 0.473413/0.020623/0.542688 | 0.433183/0.015393/0.470967 | 0.017249/0.003898/0.024629 | 0.450264/0.015897/0.495433 |
| `L0 Stage 2 / checked-runtime modes and provenance completion full / hashmap_bench / --build`  | 1.522768/0.111998/1.685252 | 1.431718/0.066518/1.525960 | 0.113719/0.020342/0.140018 | 1.542500/0.079548/1.664452 |
| `L0 Stage 2 / checked-runtime modes and provenance completion full / hashmap_bench / --gen`    | 0.465142/0.037686/0.553565 | 0.431576/0.028952/0.481521 | 0.016876/0.006516/0.024892 | 0.449965/0.035430/0.506232 |
| `L0 Stage 2 / checked-runtime modes and provenance completion basic / hashmap_bench / --build` | 1.420912/0.103628/1.620509 | 1.334709/0.057690/1.434954 | 0.107340/0.015931/0.135237 | 1.441052/0.072301/1.566351 |
| `L0 Stage 2 / checked-runtime modes and provenance completion basic / hashmap_bench / --gen`   | 0.384016/0.028383/0.470353 | 0.348147/0.017970/0.392909 | 0.015994/0.004502/0.023251 | 0.363579/0.021549/0.415495 |
| `L1 Stage 1 / 1.1.0 release baseline / hello / --build`                                        | 1.138502/0.073612/1.287192 | 1.059769/0.036357/1.133738 | 0.107622/0.011256/0.124863 | 1.169254/0.040129/1.261300 |
| `L1 Stage 1 / 1.1.0 release baseline / hello / --gen`                                          | 0.249391/0.017159/0.300221 | 0.219799/0.008307/0.244211 | 0.015559/0.003793/0.021392 | 0.235763/0.011641/0.266112 |
| `L1 Stage 1 / 1.1.0 release baseline / hamurabi / --build`                                     | 1.265339/0.099187/1.595142 | 1.178251/0.065354/1.394783 | 0.110124/0.023317/0.147180 | 1.288396/0.079976/1.541963 |
| `L1 Stage 1 / 1.1.0 release baseline / hamurabi / --gen`                                       | 0.273199/0.039742/0.367045 | 0.244687/0.016435/0.303310 | 0.016660/0.004511/0.026803 | 0.259981/0.023187/0.329893 |
| `L1 Stage 1 / 1.1.0 release baseline / hashmap_bench / --build`                                | 0.661396/0.062981/0.784495 | 0.601188/0.032445/0.659906 | 0.094299/0.013669/0.126046 | 0.695821/0.050385/0.780152 |
| `L1 Stage 1 / 1.1.0 release baseline / hashmap_bench / --gen`                                  | 0.131794/0.011683/0.168175 | 0.107182/0.007085/0.125263 | 0.010652/0.003109/0.017097 | 0.118673/0.009129/0.141015 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot full / hello / --build`                           | 2.482023/0.305039/2.902552 | 2.325970/0.189115/2.596793 | 0.127715/0.036657/0.175174 | 2.459818/0.225100/2.764282 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot full / hello / --gen`                             | 1.342167/0.110712/1.607326 | 1.278568/0.081568/1.400351 | 0.031363/0.014431/0.057681 | 1.311342/0.095198/1.457644 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot full / hamurabi / --build`                        | 2.863198/0.308862/3.368785 | 2.725036/0.220108/3.004572 | 0.141878/0.036363/0.226264 | 2.865824/0.262109/3.218601 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot full / hamurabi / --gen`                          | 1.549920/0.232790/2.235435 | 1.469080/0.093952/1.765886 | 0.038272/0.013337/0.085737 | 1.510499/0.108227/1.859013 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot full / hashmap_bench / --build`                   | 1.563559/0.142653/1.934506 | 1.478484/0.073559/1.643290 | 0.110238/0.014931/0.138800 | 1.588810/0.080617/1.778773 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot full / hashmap_bench / --gen`                     | 0.657802/0.052208/0.740306 | 0.621608/0.031362/0.660483 | 0.019293/0.009257/0.027587 | 0.639975/0.039261/0.687724 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot basic / hello / --build`                          | 2.105791/0.210450/2.543352 | 1.993070/0.112369/2.234589 | 0.128964/0.033957/0.175018 | 2.117062/0.146404/2.418134 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot basic / hello / --gen`                            | 1.018824/0.096855/1.362048 | 0.966168/0.055636/1.116760 | 0.027412/0.010452/0.059936 | 0.994691/0.065913/1.177505 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot basic / hamurabi / --build`                       | 2.459335/0.194735/2.768063 | 2.336806/0.107452/2.543992 | 0.130066/0.020558/0.172551 | 2.468227/0.129394/2.716916 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot basic / hamurabi / --gen`                         | 1.160982/0.073597/1.295276 | 1.108258/0.048480/1.166740 | 0.030227/0.007419/0.042236 | 1.139502/0.055358/1.209644 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot basic / hashmap_bench / --build`                  | 1.419203/0.149026/1.560876 | 1.336781/0.100185/1.434113 | 0.110972/0.020027/0.137554 | 1.444702/0.117247/1.564702 |
| `L1 Stage 1 / 2026-07-15 assessment snapshot basic / hashmap_bench / --gen`                    | 0.520520/0.053893/0.614577 | 0.481652/0.034665/0.548496 | 0.018635/0.005753/0.028947 | 0.499748/0.042106/0.576957 |
| `L1 Stage 1 / pre-pointer-validation snapshot / hashmap_bench / --build`                       | 0.662895/0.043713/0.730277 | 0.600745/0.019114/0.631051 | 0.097176/0.015107/0.114917 | 0.697165/0.033223/0.744805 |
| `L1 Stage 1 / pre-pointer-validation snapshot / hashmap_bench / --gen`                         | 0.133843/0.007910/0.162431 | 0.107524/0.004365/0.121708 | 0.011301/0.002672/0.016284 | 0.119073/0.007327/0.137964 |
| `L1 Stage 1 / pointer-validation introduction full / hashmap_bench / --build`                  | 1.573160/0.140584/1.747634 | 1.491595/0.088020/1.586493 | 0.110762/0.024775/0.131484 | 1.602748/0.114817/1.722497 |
| `L1 Stage 1 / pointer-validation introduction full / hashmap_bench / --gen`                    | 0.666939/0.050496/0.752894 | 0.623644/0.031260/0.663261 | 0.019241/0.008010/0.031812 | 0.642309/0.039382/0.692103 |
| `L1 Stage 1 / post-allocation-record-optimization snapshot full / hashmap_bench / --build`     | 1.567028/0.169823/2.122981 | 1.486676/0.110121/1.712484 | 0.113798/0.031583/0.172975 | 1.598386/0.143744/1.878588 |
| `L1 Stage 1 / post-allocation-record-optimization snapshot full / hashmap_bench / --gen`       | 0.655248/0.052114/0.760551 | 0.612283/0.031072/0.668508 | 0.018967/0.008547/0.032754 | 0.632642/0.041329/0.699931 |
| `L1 Stage 1 / checked-runtime modes and provenance completion full / hashmap_bench / --build`  | 1.578621/0.164297/2.014624 | 1.493133/0.065572/1.763595 | 0.110166/0.016060/0.168625 | 1.602762/0.079178/1.932829 |
| `L1 Stage 1 / checked-runtime modes and provenance completion full / hashmap_bench / --gen`    | 0.667891/0.084032/0.909312 | 0.623770/0.049024/0.734513 | 0.021304/0.008759/0.040064 | 0.645565/0.054865/0.769918 |
| `L1 Stage 1 / checked-runtime modes and provenance completion basic / hashmap_bench / --build` | 1.434038/0.075238/1.652335 | 1.344436/0.054875/1.446691 | 0.112801/0.022370/0.145304 | 1.457379/0.076985/1.591995 |
| `L1 Stage 1 / checked-runtime modes and provenance completion basic / hashmap_bench / --gen`   | 0.512835/0.036063/0.694016 | 0.473391/0.022228/0.574294 | 0.017440/0.006986/0.035955 | 0.491816/0.028382/0.613547 |
| `L0 Python Stage 1 / 1.1.0 release baseline / hello / --build`                                 | 1.084047/0.120023/1.252978 | 0.975977/0.051326/1.056672 | 0.135631/0.027281/0.169728 | 1.111002/0.085370/1.212953 |
| `L0 Python Stage 1 / 1.1.0 release baseline / hello / --gen`                                   | 0.368875/0.035369/0.494568 | 0.308146/0.015622/0.356441 | 0.042854/0.010157/0.058501 | 0.351901/0.024113/0.414943 |
| `L0 Python Stage 1 / 1.1.0 release baseline / hamurabi / --build`                              | 1.586491/0.126218/1.802176 | 1.467765/0.075923/1.562818 | 0.140640/0.018204/0.179861 | 1.607788/0.098705/1.742679 |
| `L0 Python Stage 1 / 1.1.0 release baseline / hamurabi / --gen`                                | 0.480915/0.061157/0.641775 | 0.416460/0.028331/0.468069 | 0.044118/0.008822/0.061382 | 0.462256/0.038924/0.529451 |
| `L0 Python Stage 1 / 1.1.0 release baseline / hashmap_bench / --build`                         | 1.231200/0.073984/1.479021 | 1.122801/0.046667/1.246724 | 0.132528/0.017909/0.166379 | 1.254994/0.061433/1.413103 |
| `L0 Python Stage 1 / 1.1.0 release baseline / hashmap_bench / --gen`                           | 0.392704/0.023381/0.479043 | 0.335176/0.013432/0.365446 | 0.041623/0.006370/0.054012 | 0.377010/0.019552/0.419751 |
| `L0 Python Stage 1 / 2026-07-15 assessment snapshot / hello / --build`                         | 1.260654/0.101412/1.517792 | 1.150521/0.063162/1.316264 | 0.134778/0.019835/0.175219 | 1.284503/0.088852/1.488828 |
| `L0 Python Stage 1 / 2026-07-15 assessment snapshot / hello / --gen`                           | 0.367362/0.018583/0.437671 | 0.308461/0.012685/0.334375 | 0.041976/0.006190/0.055412 | 0.352025/0.019040/0.385560 |
| `L0 Python Stage 1 / 2026-07-15 assessment snapshot / hamurabi / --build`                      | 1.859894/0.151670/2.073640 | 1.739113/0.093348/1.848734 | 0.138535/0.027878/0.183017 | 1.881091/0.122310/2.033910 |
| `L0 Python Stage 1 / 2026-07-15 assessment snapshot / hamurabi / --gen`                        | 0.479057/0.031457/0.558054 | 0.418059/0.014402/0.447962 | 0.043631/0.005059/0.059859 | 0.461553/0.018493/0.506527 |
| `L0 Python Stage 1 / 2026-07-15 assessment snapshot / hashmap_bench / --build`                 | 1.451112/0.139049/1.735316 | 1.335353/0.088742/1.488855 | 0.140163/0.028761/0.185362 | 1.472609/0.103033/1.661838 |
| `L0 Python Stage 1 / 2026-07-15 assessment snapshot / hashmap_bench / --gen`                   | 0.412741/0.028213/0.612553 | 0.344702/0.011134/0.433382 | 0.045010/0.008948/0.066680 | 0.389767/0.016484/0.498567 |

## Implementation Confirmation (2026-07-16)

A non-gating confirmation run measured the implemented default against explicit basic and explicit full compiler builds.
All three variants retained the 256-record compiler quarantine cap; the default and explicit-basic variants selected
basic checked validation for the compiler executable, while the explicit-full variant disabled the compiler basic-mode
default. Compilers used `-O2`; sources, sysroots, workloads, C compiler, build options, and generated-program runtime
mode matched the historical assessment. No timed command passed `--check-basic`.

Preflight passed 36/36 compile cases, 12/12 hello/hashmap executable runs, and 6/6 L0/L1 workload groups with
byte-identical generated C across default, explicit-basic, and explicit-full compiler binaries. Collection used the same
fixed seed, two randomized warmup blocks, and 30 randomized measured blocks. All 72 warmup invocations and 1,080
measured samples succeeded; every measured sample was retained without outlier filtering.

The run detected no difference between the new default and the explicit-basic control: all 24 wall/total-CPU bootstrap
intervals include no change. The compiler-only result remains clear. Explicit basic versus full reduces `--gen` median
wall time by 16.2 to 18.2 percent for L0 and 21.4 to 22.8 percent for L1; all six wall intervals exclude no change.
Total CPU falls by 16.4 to 18.7 percent for L0 and 22.0 to 23.7 percent for L1, again with every interval excluding no
change.

As before, C compilation and linking dilute the compiler-runtime effect. L0 `--build` medians favor explicit basic by
3.1 to 6.0 percent in wall time, but none of the six wall/CPU intervals excludes no change. L1 `--build` wall medians
favor explicit basic by 7.5 to 14.0 percent; only the hashmap wall and total-CPU intervals exclude no change. These
non-gating results confirm the default selection without turning host timing variance into a correctness requirement.

### Complete Descriptive Statistics

All values are seconds. Each metric reports median / IQR / p95; `n=30` for every cell.

| Level      | Workload        | Operation | Compiler mode  |                  Wall |              User CPU |            System CPU |             Total CPU |
| ---------- | --------------- | --------- | -------------- | --------------------: | --------------------: | --------------------: | --------------------: |
| L0 Stage 2 | `hello`         | `--build` | default        | 0.840 / 0.278 / 1.297 | 0.801 / 0.230 / 1.144 | 0.070 / 0.034 / 0.121 | 0.869 / 0.262 / 1.255 |
| L0 Stage 2 | `hello`         | `--gen`   | default        | 0.215 / 0.077 / 0.308 | 0.195 / 0.061 / 0.271 | 0.010 / 0.006 / 0.019 | 0.205 / 0.071 / 0.287 |
| L0 Stage 2 | `hamurabi`      | `--build` | default        | 1.366 / 0.581 / 2.592 | 1.315 / 0.448 / 2.223 | 0.076 / 0.043 / 0.168 | 1.390 / 0.507 / 2.404 |
| L0 Stage 2 | `hamurabi`      | `--gen`   | default        | 0.412 / 0.164 / 0.642 | 0.389 / 0.148 / 0.579 | 0.014 / 0.009 / 0.028 | 0.402 / 0.158 / 0.609 |
| L0 Stage 2 | `hashmap_bench` | `--build` | default        | 0.986 / 0.364 / 1.438 | 0.944 / 0.313 / 1.362 | 0.072 / 0.037 / 0.113 | 1.016 / 0.352 / 1.473 |
| L0 Stage 2 | `hashmap_bench` | `--gen`   | default        | 0.258 / 0.083 / 0.448 | 0.242 / 0.074 / 0.388 | 0.009 / 0.005 / 0.022 | 0.251 / 0.079 / 0.410 |
| L0 Stage 2 | `hello`         | `--build` | explicit basic | 0.834 / 0.244 / 1.247 | 0.784 / 0.206 / 1.121 | 0.070 / 0.028 / 0.119 | 0.856 / 0.234 / 1.241 |
| L0 Stage 2 | `hello`         | `--gen`   | explicit basic | 0.207 / 0.050 / 0.311 | 0.190 / 0.041 / 0.279 | 0.009 / 0.005 / 0.017 | 0.197 / 0.046 / 0.294 |
| L0 Stage 2 | `hamurabi`      | `--build` | explicit basic | 1.355 / 0.545 / 2.161 | 1.298 / 0.470 / 1.963 | 0.076 / 0.045 / 0.140 | 1.371 / 0.524 / 2.116 |
| L0 Stage 2 | `hamurabi`      | `--gen`   | explicit basic | 0.407 / 0.127 / 0.595 | 0.383 / 0.114 / 0.547 | 0.013 / 0.008 / 0.024 | 0.397 / 0.121 / 0.569 |
| L0 Stage 2 | `hashmap_bench` | `--build` | explicit basic | 0.983 / 0.338 / 1.449 | 0.940 / 0.302 / 1.365 | 0.069 / 0.034 / 0.114 | 1.007 / 0.342 / 1.475 |
| L0 Stage 2 | `hashmap_bench` | `--gen`   | explicit basic | 0.272 / 0.083 / 0.404 | 0.253 / 0.067 / 0.358 | 0.011 / 0.006 / 0.020 | 0.262 / 0.073 / 0.377 |
| L0 Stage 2 | `hello`         | `--build` | explicit full  | 0.861 / 0.308 / 1.334 | 0.820 / 0.259 / 1.232 | 0.068 / 0.028 / 0.126 | 0.886 / 0.288 / 1.352 |
| L0 Stage 2 | `hello`         | `--gen`   | explicit full  | 0.249 / 0.056 / 0.383 | 0.230 / 0.053 / 0.349 | 0.009 / 0.005 / 0.017 | 0.240 / 0.055 / 0.366 |
| L0 Stage 2 | `hamurabi`      | `--build` | explicit full  | 1.423 / 0.489 / 2.253 | 1.378 / 0.424 / 2.108 | 0.076 / 0.036 / 0.153 | 1.450 / 0.467 / 2.256 |
| L0 Stage 2 | `hamurabi`      | `--gen`   | explicit full  | 0.498 / 0.199 / 0.768 | 0.474 / 0.177 / 0.705 | 0.014 / 0.010 / 0.028 | 0.487 / 0.189 / 0.733 |
| L0 Stage 2 | `hashmap_bench` | `--build` | explicit full  | 1.047 / 0.258 / 1.701 | 1.006 / 0.238 / 1.539 | 0.068 / 0.024 / 0.126 | 1.073 / 0.258 / 1.665 |
| L0 Stage 2 | `hashmap_bench` | `--gen`   | explicit full  | 0.324 / 0.128 / 0.529 | 0.305 / 0.105 / 0.455 | 0.009 / 0.007 / 0.020 | 0.314 / 0.114 / 0.476 |
| L1 Stage 1 | `hello`         | `--build` | default        | 1.468 / 0.528 / 2.231 | 1.415 / 0.477 / 2.036 | 0.080 / 0.037 / 0.134 | 1.498 / 0.523 / 2.170 |
| L1 Stage 1 | `hello`         | `--gen`   | default        | 0.745 / 0.294 / 1.092 | 0.715 / 0.264 / 0.998 | 0.016 / 0.012 / 0.035 | 0.732 / 0.279 / 1.033 |
| L1 Stage 1 | `hamurabi`      | `--build` | default        | 1.724 / 0.676 / 2.673 | 1.649 / 0.562 / 2.473 | 0.082 / 0.050 / 0.176 | 1.731 / 0.607 / 2.642 |
| L1 Stage 1 | `hamurabi`      | `--gen`   | default        | 0.806 / 0.230 / 1.197 | 0.771 / 0.218 / 1.119 | 0.016 / 0.007 / 0.038 | 0.787 / 0.224 / 1.157 |
| L1 Stage 1 | `hashmap_bench` | `--build` | default        | 1.018 / 0.370 / 1.441 | 0.976 / 0.327 / 1.355 | 0.074 / 0.035 / 0.116 | 1.048 / 0.369 / 1.471 |
| L1 Stage 1 | `hashmap_bench` | `--gen`   | default        | 0.336 / 0.086 / 0.532 | 0.318 / 0.081 / 0.484 | 0.009 / 0.004 / 0.023 | 0.327 / 0.084 / 0.505 |
| L1 Stage 1 | `hello`         | `--build` | explicit basic | 1.460 / 0.540 / 2.232 | 1.412 / 0.448 / 2.000 | 0.080 / 0.047 / 0.138 | 1.487 / 0.495 / 2.128 |
| L1 Stage 1 | `hello`         | `--gen`   | explicit basic | 0.730 / 0.201 / 1.041 | 0.707 / 0.190 / 0.990 | 0.016 / 0.009 / 0.030 | 0.721 / 0.196 / 1.020 |
| L1 Stage 1 | `hamurabi`      | `--build` | explicit basic | 1.756 / 0.524 / 2.404 | 1.682 / 0.475 / 2.274 | 0.084 / 0.040 / 0.145 | 1.766 / 0.511 / 2.408 |
| L1 Stage 1 | `hamurabi`      | `--gen`   | explicit basic | 0.810 / 0.221 / 1.215 | 0.769 / 0.214 / 1.132 | 0.017 / 0.009 / 0.038 | 0.786 / 0.219 / 1.174 |
| L1 Stage 1 | `hashmap_bench` | `--build` | explicit basic | 0.975 / 0.337 / 1.558 | 0.936 / 0.284 / 1.442 | 0.069 / 0.039 / 0.139 | 1.003 / 0.325 / 1.573 |
| L1 Stage 1 | `hashmap_bench` | `--gen`   | explicit basic | 0.352 / 0.094 / 0.544 | 0.331 / 0.086 / 0.501 | 0.010 / 0.004 / 0.023 | 0.341 / 0.090 / 0.522 |
| L1 Stage 1 | `hello`         | `--build` | explicit full  | 1.698 / 0.409 / 2.517 | 1.641 / 0.369 / 2.343 | 0.083 / 0.031 / 0.152 | 1.722 / 0.401 / 2.484 |
| L1 Stage 1 | `hello`         | `--gen`   | explicit full  | 0.939 / 0.374 / 1.415 | 0.907 / 0.339 / 1.328 | 0.016 / 0.015 / 0.040 | 0.924 / 0.358 / 1.368 |
| L1 Stage 1 | `hamurabi`      | `--build` | explicit full  | 1.898 / 0.352 / 3.076 | 1.843 / 0.321 / 2.802 | 0.081 / 0.021 / 0.172 | 1.923 / 0.343 / 2.975 |
| L1 Stage 1 | `hamurabi`      | `--gen`   | explicit full  | 1.030 / 0.303 / 1.619 | 0.997 / 0.285 / 1.524 | 0.018 / 0.014 / 0.046 | 1.013 / 0.297 / 1.565 |
| L1 Stage 1 | `hashmap_bench` | `--build` | explicit full  | 1.089 / 0.417 / 1.707 | 1.037 / 0.329 / 1.502 | 0.073 / 0.036 / 0.127 | 1.110 / 0.370 / 1.629 |
| L1 Stage 1 | `hashmap_bench` | `--gen`   | explicit full  | 0.457 / 0.120 / 0.679 | 0.437 / 0.117 / 0.623 | 0.011 / 0.006 / 0.022 | 0.447 / 0.120 / 0.646 |

### Bootstrap Comparisons

Each cell is the comparison/reference median percentage delta with a 95% percentile-bootstrap confidence interval
(10,000 resamples, seed 20,260,715). Negative means the comparison compiler is faster or uses less CPU.

| Level | Workload        | Operation | Comparison                |                    Wall |               Total CPU |
| ----- | --------------- | --------- | ------------------------- | ----------------------: | ----------------------: |
| L0    | `hello`         | `--build` | explicit basic vs default |  -0.7% [-13.5%, +10.1%] |  -1.5% [-11.6%, +10.4%] |
| L0    | `hello`         | `--build` | explicit full vs default  |   +2.4% [-9.5%, +19.7%] |   +2.0% [-7.7%, +17.2%] |
| L0    | `hello`         | `--build` | explicit basic vs full    |   -3.1% [-16.8%, +6.7%] |   -3.4% [-15.6%, +6.6%] |
| L0    | `hello`         | `--gen`   | explicit basic vs default |   -3.7% [-17.4%, +7.1%] |   -3.8% [-17.1%, +6.9%] |
| L0    | `hello`         | `--gen`   | explicit full vs default  |  +15.6% [-0.5%, +28.8%] |  +16.8% [+0.6%, +28.7%] |
| L0    | `hello`         | `--gen`   | explicit basic vs full    |  -16.7% [-24.3%, -9.1%] |  -17.7% [-24.8%, -9.5%] |
| L0    | `hamurabi`      | `--build` | explicit basic vs default |  -0.8% [-13.6%, +23.3%] |  -1.3% [-13.3%, +23.0%] |
| L0    | `hamurabi`      | `--build` | explicit full vs default  |   +4.2% [-9.1%, +20.8%] |   +4.3% [-8.3%, +19.8%] |
| L0    | `hamurabi`      | `--build` | explicit basic vs full    |  -4.8% [-17.7%, +18.4%] |  -5.4% [-16.7%, +17.5%] |
| L0    | `hamurabi`      | `--gen`   | explicit basic vs default |  -1.2% [-20.6%, +14.0%] |  -1.3% [-19.6%, +13.1%] |
| L0    | `hamurabi`      | `--gen`   | explicit full vs default  |  +20.8% [-2.2%, +44.6%] |  +21.3% [-0.0%, +46.5%] |
| L0    | `hamurabi`      | `--gen`   | explicit basic vs full    |  -18.2% [-32.0%, -8.9%] |  -18.7% [-31.9%, -9.9%] |
| L0    | `hashmap_bench` | `--build` | explicit basic vs default |  -0.3% [-15.5%, +18.8%] |  -0.9% [-14.4%, +19.7%] |
| L0    | `hashmap_bench` | `--build` | explicit full vs default  |  +6.1% [-10.2%, +16.6%] |   +5.6% [-9.7%, +15.4%] |
| L0    | `hashmap_bench` | `--build` | explicit basic vs full    |  -6.0% [-15.1%, +11.9%] |  -6.1% [-13.4%, +13.4%] |
| L0    | `hashmap_bench` | `--gen`   | explicit basic vs default |   +5.2% [-7.3%, +18.8%] |   +4.7% [-7.0%, +17.0%] |
| L0    | `hashmap_bench` | `--gen`   | explicit full vs default  |  +25.5% [+8.7%, +39.3%] | +25.2% [+10.0%, +40.1%] |
| L0    | `hashmap_bench` | `--gen`   | explicit basic vs full    |  -16.2% [-23.8%, -4.1%] |  -16.4% [-23.9%, -6.6%] |
| L1    | `hello`         | `--build` | explicit basic vs default |  -0.5% [-12.0%, +24.6%] |  -0.7% [-10.4%, +23.0%] |
| L1    | `hello`         | `--build` | explicit full vs default  |  +15.6% [+1.9%, +28.4%] |  +15.0% [+3.3%, +27.5%] |
| L1    | `hello`         | `--build` | explicit basic vs full    |  -14.0% [-23.1%, +7.8%] |  -13.6% [-22.5%, +6.8%] |
| L1    | `hello`         | `--gen`   | explicit basic vs default |  -2.1% [-18.1%, +12.5%] |  -1.5% [-18.2%, +11.8%] |
| L1    | `hello`         | `--gen`   | explicit full vs default  |  +26.0% [+8.0%, +47.8%] |  +26.2% [+8.8%, +48.9%] |
| L1    | `hello`         | `--gen`   | explicit basic vs full    | -22.3% [-34.0%, -12.1%] | -22.0% [-34.2%, -12.5%] |
| L1    | `hamurabi`      | `--build` | explicit basic vs default |  +1.8% [-15.4%, +15.5%] |  +2.0% [-14.6%, +14.2%] |
| L1    | `hamurabi`      | `--build` | explicit full vs default  |  +10.1% [-4.9%, +25.5%] |  +11.0% [-4.4%, +23.7%] |
| L1    | `hamurabi`      | `--build` | explicit basic vs full    |   -7.5% [-20.5%, +3.1%] |   -8.2% [-19.4%, +1.4%] |
| L1    | `hamurabi`      | `--gen`   | explicit basic vs default |    +0.5% [-9.8%, +8.5%] |    -0.1% [-8.6%, +8.0%] |
| L1    | `hamurabi`      | `--gen`   | explicit full vs default  | +27.9% [+18.7%, +49.0%] | +28.7% [+20.1%, +50.3%] |
| L1    | `hamurabi`      | `--gen`   | explicit basic vs full    | -21.4% [-33.6%, -16.5%] | -22.4% [-34.1%, -17.0%] |
| L1    | `hashmap_bench` | `--build` | explicit basic vs default |   -4.2% [-15.7%, +6.3%] |   -4.3% [-15.6%, +5.9%] |
| L1    | `hashmap_bench` | `--build` | explicit full vs default  |   +7.0% [-5.9%, +34.5%] |   +5.9% [-4.7%, +32.6%] |
| L1    | `hashmap_bench` | `--build` | explicit basic vs full    |  -10.4% [-28.7%, -2.4%] |   -9.6% [-27.3%, -2.3%] |
| L1    | `hashmap_bench` | `--gen`   | explicit basic vs default |   +4.7% [-6.1%, +12.3%] |   +4.2% [-5.8%, +12.0%] |
| L1    | `hashmap_bench` | `--gen`   | explicit full vs default  | +35.8% [+22.9%, +54.9%] | +36.7% [+24.1%, +52.0%] |
| L1    | `hashmap_bench` | `--gen`   | explicit basic vs full    | -22.8% [-33.0%, -17.4%] | -23.7% [-32.4%, -18.1%] |

Raw samples, build logs, compiler binaries, and temporary paths are intentionally not retained in the source tree.
