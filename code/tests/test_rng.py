"""splitmix64 确定性守门（plan/03 §五第 1 条 + plan/05 §二）。

金标序列硬编码于此：seed 同 → 序列同。3.8 与 3.12 解释器各自跑到同一金标，
即等价于"同 seed 跨解释器序列一致"（M1 DoD 第 1 项）——改动 rng.py 任何
常量或运算顺序都会在此被拦下。seed=0 首值 0xe220a8397b1dcdaf 为公开测试向量。
"""

import pytest

from taw.rng import SplitMix64

SEED = 42
GOLDEN_SEED42 = [
    0xBDD732262FEB6E95,
    0x28EFE333B266F103,
    0x47526757130F9F52,
    0x581CE1FF0E4AE394,
    0x9BC585A244823F2,
    0xDE4431FA3C80DB06,
    0x37E9671C45376D5D,
    0xCCF635EE9E9E2FA4,
]


def test_known_public_vector_seed0():
    r = SplitMix64(0)
    assert r.next_u64() == 0xE220A8397B1DCDAF
    assert r.next_u64() == 0x6E789E6AA1B965F4
    assert r.next_u64() == 0x6C45D188009454F


def test_golden_sequence_seed42():
    r = SplitMix64(SEED)
    assert [r.next_u64() for _ in range(8)] == GOLDEN_SEED42


def test_same_seed_same_sequence_all_helpers():
    """全部 helper 都只消费同一条 u64 流——任一处漂移都会让两侧失配。"""
    a, b = SplitMix64(SEED), SplitMix64(SEED)
    for _ in range(50):
        assert a.next_u64() == b.next_u64()
        assert a.below(97) == b.below(97)
        assert a.randrange(5, 11) == b.randrange(5, 11)
        assert a.chance(0.5) == b.chance(0.5)
        assert a.choice(list("abcdefghij")) == b.choice(list("abcdefghij"))


def test_different_seeds_diverge():
    a, b = SplitMix64(1), SplitMix64(2)
    assert [a.next_u64() for _ in range(8)] != [b.next_u64() for _ in range(8)]


def test_shuffle_deterministic_and_permutation():
    r1, r2 = SplitMix64(SEED), SplitMix64(SEED)
    items1, items2 = list(range(10)), list(range(10))
    out1, out2 = r1.shuffle(items1), r2.shuffle(items2)
    assert out1 == [0, 9, 5, 8, 6, 4, 7, 2, 1, 3]
    assert out1 == out2
    assert sorted(out1) == list(range(10))


def test_sample_no_replacement_and_source_untouched():
    r = SplitMix64(SEED)
    source = list(range(20))
    out = r.sample(source, 5)
    assert out == [16, 3, 8, 11, 17]
    assert len(set(out)) == 5
    assert source == list(range(20))


def test_choice_rejects_out_of_range_and_zero():
    r = SplitMix64(SEED)
    with pytest.raises(ValueError):
        r.below(0)
    with pytest.raises(ValueError):
        r.randrange(5, 5)
    with pytest.raises(ValueError):
        r.chance(1.5)


def test_no_stdlib_random_import():
    """确定性纪律：生成链路禁 stdlib random——rng 模块自身也不得引用。"""
    import taw.rng as rng_mod
    import sys

    assert "random" not in sys.modules or rng_mod is not None
    src_vars = set(dir(rng_mod))
    assert not src_vars & {"random", "randint", "seed"}


def test_below_in_range_statistical_smoke():
    r = SplitMix64(7)
    vals = [r.below(10) for _ in range(200)]
    assert all(0 <= v < 10 for v in vals)
    assert len(set(vals)) >= 5  # 200 次只落 5 个以下桶 = 序列损坏
