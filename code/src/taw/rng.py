"""splitmix64 确定性 RNG（plan/03 §五第 1 条确定性纪律的实现载体）。

生成器禁 stdlib random / set 迭代序 / 系统时钟——本模块是唯一随机源：
纯 64 位整数运算，无外部状态，同 seed 跨解释器（3.8/3.12）序列逐值一致；
金标序列锁定在 tests/test_rng.py，改动任何常量或运算顺序都会被它大声拦下。
"""

MASK64 = 0xFFFFFFFFFFFFFFFF
_GOLDEN = 0x9E3779B97F4A7C15
_U64_COUNT = 1 << 64


class SplitMix64:
    """splitmix64：state 每次 +GOLDEN，再三次混合（Steele/Lea/Batson 算法）。"""

    def __init__(self, seed):
        self._state = seed & MASK64

    def next_u64(self):
        self._state = (self._state + _GOLDEN) & MASK64
        z = self._state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return z ^ (z >> 31)

    def below(self, n):
        """[0, n) 整数。splitmix64 输出全域均匀，取模偏差在生成器规模下可忽略。"""
        if n <= 0:
            raise ValueError("below() 要求 n >= 1，得到 {}".format(n))
        return self.next_u64() % n

    def randrange(self, lo, hi):
        """[lo, hi) 整数；hi <= lo 时 ValueError（与 stdlib random 语义不同处：不接受单参）。"""
        if hi <= lo:
            raise ValueError("randrange(lo, hi) 要求 hi > lo，得到 ({}, {})".format(lo, hi))
        return lo + self.below(hi - lo)

    def chance(self, p):
        """以概率 p 返回 True（p 用定点数比较：next_u64 < p * 2^64）。"""
        if not 0.0 <= p <= 1.0:
            raise ValueError("chance() 概率必须在 [0, 1]，得到 {}".format(p))
        return self.next_u64() < int(p * _U64_COUNT)

    def choice(self, seq):
        """按 index 取元素——只接受序列，禁止传 set（迭代序不定，违反确定性纪律）。"""
        return seq[self.below(len(seq))]

    def shuffle(self, items):
        """Fisher-Yates 就地洗牌（要求 list；返回同一对象便于链式书写）。"""
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]
        return items

    def sample(self, seq, k):
        """无放回取 k 个（拷贝后洗牌取前 k，不动原序列）。"""
        if k > len(seq):
            raise ValueError("sample(k={}) 超过序列长度 {}".format(k, len(seq)))
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]
