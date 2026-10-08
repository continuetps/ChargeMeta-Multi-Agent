from chargemeta.services.search import _rrf


def test_rrf_fuses_multiple_rankings():
    scores = _rrf([[1, 2, 3], [2, 1, 4]])
    assert scores[1] > scores[3]
    assert scores[2] > scores[4]
