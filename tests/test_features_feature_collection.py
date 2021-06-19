"""Tests for the features functionality."""

__author__ = "Jeroen Van Der Donckt, Emiel Deprost, Jonas Van Der Donckt"

import pytest
import warnings
import pandas as pd
import numpy as np

from tsflex.features import NumpyFuncWrapper
from tsflex.features import FeatureDescriptor, MultipleFeatureDescriptors
from tsflex.features import FeatureCollection

from pandas.testing import assert_index_equal, assert_frame_equal
from typing import Tuple
from .utils import dummy_data


## FeatureCollection


def test_single_series_feature_collection(dummy_data):
    fd = FeatureDescriptor(
        function=np.sum,
        series_name="EDA",
        window="5s",
        stride="2.5s",
    )
    fc = FeatureCollection(feature_descriptors=fd)

    assert fc.get_required_series() == ["EDA"]

    res_list = fc.calculate(dummy_data, return_df=False, n_jobs=1)
    res_df = fc.calculate(dummy_data, return_df=True, n_jobs=1)

    assert isinstance(res_list, list) & (len(res_list) == 1)
    assert isinstance(res_df, pd.DataFrame)
    assert_frame_equal(res_list[0], res_df)
    freq = pd.to_timedelta(pd.infer_freq(dummy_data.index)) / np.timedelta64(1, "s")
    stride_s = 2.5
    window_s = 5
    assert len(res_df) == (int(len(dummy_data) / (1 / freq)) - window_s) // stride_s
    assert all(res_df.index[1:] - res_df.index[:-1] == pd.to_timedelta(2.5, unit="s"))


def test_uneven_sampled_series_feature_collection(dummy_data):
    fd = FeatureDescriptor(
        function=np.sum,
        series_name="EDA",
        window="5s",
        stride="2.5s",
    )
    fc = FeatureCollection(feature_descriptors=fd)
    fc.add(FeatureDescriptor(np.min, series_name=("TMP",), window=5, stride=2.5))
    fc.add(FeatureDescriptor(np.min, series_name=("EDA",), window=5, stride=2.5))

    assert set(fc.get_required_series()) == set(["EDA", "TMP"])
    assert len(fc.get_required_series()) == 2

    # Drop some data to obtain an irregular sampling rate
    inp = dummy_data.drop(np.random.choice(dummy_data.index[1:-1], 500, replace=False))

    res_df = fc.calculate(inp, return_df=True, approve_sparsity=True, n_jobs=3)

    assert res_df.shape[1] == 3
    freq = pd.to_timedelta(pd.infer_freq(dummy_data.index)) / np.timedelta64(1, "s")
    stride_s = 2.5
    window_s = 5
    assert len(res_df) == (int(len(dummy_data) / (1 / freq)) - window_s) // stride_s
    assert all(res_df.index[1:] - res_df.index[:-1] == pd.to_timedelta(2.5, unit="s"))


def test_warning_uneven_sampled_series_feature_collection(dummy_data):
    fd = FeatureDescriptor(
        function=np.sum,
        series_name="EDA",
        window="5s",
        stride="2.5s",
    )
    fc = FeatureCollection(feature_descriptors=fd)
    fc.add(FeatureDescriptor(np.min, series_name=("TMP",), window=5, stride=2.5))

    assert set(fc.get_required_series()) == set(["EDA", "TMP"])
    assert len(fc.get_required_series()) == 2

    # Drop some data to obtain an irregular sampling rate
    inp = dummy_data.drop(np.random.choice(dummy_data.index[1:-1], 500, replace=False))

    with warnings.catch_warnings(record=True) as w:
        # Trigger the warning
        res_df = fc.calculate(inp, return_df=True, approve_sparsity=False)
        # Verify the warning
        assert len(w) == 2
        assert all([issubclass(warn.category, RuntimeWarning) for warn in w])
        assert all(["gaps in the time-series" in str(warn) for warn in w])
        # Check the output
        assert res_df.shape[1] == 2
        freq = pd.to_timedelta(pd.infer_freq(dummy_data.index)) / np.timedelta64(1, "s")
        stride_s = 2.5
        window_s = 5
        assert len(res_df) == (int(len(dummy_data) / (1 / freq)) - window_s) // stride_s
        assert all(
            res_df.index[1:] - res_df.index[:-1] == pd.to_timedelta(2.5, unit="s")
        )


def test_window_idx_single_series_feature_collection(dummy_data):
    fd = FeatureDescriptor(
        function=np.sum,
        series_name="EDA",
        window="5s",
        stride="2.5s",
    )
    fc = FeatureCollection(feature_descriptors=fd)

    assert fc.get_required_series() == ["EDA"]

    res_begin = fc.calculate(dummy_data, return_df=True, window_idx="begin")
    res_end = fc.calculate(dummy_data, return_df=True, window_idx="end")
    res_middle = fc.calculate(dummy_data, return_df=True, window_idx="middle")

    assert np.isclose(res_begin.values, res_end.values).all()
    assert np.isclose(res_begin.values, res_middle.values).all()

    assert res_begin.index[0] == dummy_data.index[0]
    assert res_end.index[0] == dummy_data.index[0] + pd.to_timedelta(5, unit="s")
    assert res_middle.index[0] == dummy_data.index[0] + pd.to_timedelta(2.5, unit="s")

    for res_df in [res_begin, res_end, res_middle]:
        freq = pd.to_timedelta(pd.infer_freq(dummy_data.index)) / np.timedelta64(1, "s")
        stride_s = 2.5
        window_s = 5
        assert len(res_df) == (int(len(dummy_data) / (1 / freq)) - window_s) // stride_s
        assert all(
            res_df.index[1:] - res_df.index[:-1] == pd.to_timedelta(2.5, unit="s")
        )


def test_multiplefeaturedescriptors_feature_collection(dummy_data):
    def sum_func(sig: np.ndarray) -> float:
        return sum(sig)

    mfd = MultipleFeatureDescriptors(
        functions=[sum_func, NumpyFuncWrapper(np.max), np.min],
        series_names=["EDA", "TMP"],
        windows=["5s", "7.5s"],
        strides="2.5s",
    )
    fc = FeatureCollection(feature_descriptors=mfd)

    assert set(fc.get_required_series()) == set(["EDA", "TMP"])
    assert len(fc.get_required_series()) == 2

    res_list = fc.calculate(dummy_data, return_df=False, n_jobs=6)
    res_df = fc.calculate(dummy_data, return_df=True, n_jobs=6)

    assert (len(res_list) == 3 * 2 * 2) & (res_df.shape[1] == 3 * 2 * 2)
    res_list_names = [res.columns.values[0] for res in res_list]
    assert set(res_list_names) == set(res_df.columns)
    expected_output_names = [
        [
            f"{sig}__sum_func__w=5s_s=2.5s",
            f"{sig}__sum_func__w=7.5s_s=2.5s",
            f"{sig}__amax__w=5s_s=2.5s",
            f"{sig}__amax__w=7.5s_s=2.5s",
            f"{sig}__amin__w=5s_s=2.5s",
            f"{sig}__amin__w=7.5s_s=2.5s",
        ]
        for sig in ["EDA", "TMP"]
    ]
    # Flatten
    expected_output_names = expected_output_names[0] + expected_output_names[1]
    assert set(res_df.columns) == set(expected_output_names)

    # No NaNs when returning a list of calculated featured
    assert all([~res.isna().values.any() for res in res_list])
    # NaNs when merging to a df (for  some cols)
    assert all([res_df[col].isna().any() for col in res_df.columns if "w=7.5s" in col])
    assert all([~res_df[col].isna().any() for col in res_df.columns if "w=5s" in col])

    stride_s = 2.5
    window_s = 5
    freq = pd.to_timedelta(pd.infer_freq(dummy_data.index)) / np.timedelta64(1, "s")
    expected_length = (int(len(dummy_data) / (1 / freq)) - window_s) // stride_s
    assert all(
        [
            len(res) == expected_length - 1
            for res in res_list
            if "w=7.5s" in res.columns.values[0]
        ]
    )
    assert all(
        [
            len(res) == expected_length
            for res in res_list
            if "w=5s" in res.columns.values[0]
        ]
    )
    assert len(res_df) == expected_length


def test_featurecollection_feature_collection(dummy_data):
    fd = FeatureDescriptor(
        function=np.sum,
        series_name="EDA",
        window="5s",
        stride="2.5s",
    )
    fc = FeatureCollection(FeatureCollection(feature_descriptors=fd))

    assert fc.get_required_series() == ["EDA"]

    res_list = fc.calculate(dummy_data, return_df=False, n_jobs=1)
    res_df = fc.calculate(dummy_data, return_df=True, n_jobs=1)

    assert isinstance(res_list, list) & (len(res_list) == 1)
    assert isinstance(res_df, pd.DataFrame)
    assert_frame_equal(res_list[0], res_df)
    freq = pd.to_timedelta(pd.infer_freq(dummy_data.index)) / np.timedelta64(1, "s")
    stride_s = 2.5
    window_s = 5
    assert len(res_df) == (int(len(dummy_data) / (1 / freq)) - window_s) // stride_s
    assert all(res_df.index[1:] - res_df.index[:-1] == pd.to_timedelta(2.5, unit="s"))


### Test various feature descriptor functions


def test_one_to_many_feature_collection(dummy_data):
    def quantiles(sig: pd.Series) -> Tuple[float, float, float]:
        return np.quantile(sig, q=[0.1, 0.5, 0.9])

    q_func = NumpyFuncWrapper(quantiles, output_names=["q_0.1", "q_0.5", "q_0.9"])
    fd = FeatureDescriptor(q_func, series_name="EDA", window="5s", stride="2.5s")
    fc = FeatureCollection(fd)

    res_df = fc.calculate(dummy_data, return_df=True)
    assert res_df.shape[1] == 3
    freq = pd.to_timedelta(pd.infer_freq(dummy_data.index)) / np.timedelta64(1, "s")
    stride_s = 2.5
    window_s = 5
    assert len(res_df) == (int(len(dummy_data) / (1 / freq)) - window_s) // stride_s

    expected_output_names = [
        "EDA__q_0.1__w=5s_s=2.5s",
        "EDA__q_0.5__w=5s_s=2.5s",
        "EDA__q_0.9__w=5s_s=2.5s",
    ]
    assert set(res_df.columns.values) == set(expected_output_names)
    assert (res_df[expected_output_names[0]] != res_df[expected_output_names[1]]).any()
    assert (res_df[expected_output_names[0]] != res_df[expected_output_names[2]]).any()


def test_many_to_one_feature_collection(dummy_data):
    def abs_mean_diff(sig1: pd.Series, sig2: pd.Series) -> float:
        # Note that this func only works when sig1 and sig2 have the same length
        return np.mean(np.abs(sig1 - sig2))

    fd = FeatureDescriptor(
        abs_mean_diff, series_name=("EDA", "TMP"), window="5s", stride="2.5s"
    )
    fc = FeatureCollection(fd)

    assert set(fc.get_required_series()) == set(["EDA", "TMP"])

    res_df = fc.calculate(dummy_data, return_df=True)
    assert res_df.shape[1] == 1
    freq = pd.to_timedelta(pd.infer_freq(dummy_data.index)) / np.timedelta64(1, "s")
    stride_s = 2.5
    window_s = 5
    assert len(res_df) == (int(len(dummy_data) / (1 / freq)) - window_s) // stride_s

    expected_output_name = "EDA|TMP__abs_mean_diff__w=5s_s=2.5s"
    assert res_df.columns.values[0] == expected_output_name


def test_many_to_many_feature_collection(dummy_data):
    def quantiles_abs_diff(
        sig1: pd.Series, sig2: pd.Series
    ) -> Tuple[float, float, float]:
        return np.quantile(np.abs(sig1 - sig2), q=[0.1, 0.5, 0.9])

    q_func = NumpyFuncWrapper(
        quantiles_abs_diff,
        output_names=["q_0.1_abs_diff", "q_0.5_abs_diff", "q_0.9_abs_diff"],
    )
    fd = FeatureDescriptor(
        q_func, series_name=("EDA", "TMP"), window="5s", stride="2.5s"
    )
    fc = FeatureCollection(fd)

    assert set(fc.get_required_series()) == set(["EDA", "TMP"])

    res_df = fc.calculate(dummy_data, return_df=True)
    assert res_df.shape[1] == 3
    freq = pd.to_timedelta(pd.infer_freq(dummy_data.index)) / np.timedelta64(1, "s")
    stride_s = 2.5
    window_s = 5
    assert len(res_df) == (int(len(dummy_data) / (1 / freq)) - window_s) // stride_s

    expected_output_names = [
        "EDA|TMP__q_0.1_abs_diff__w=5s_s=2.5s",
        "EDA|TMP__q_0.5_abs_diff__w=5s_s=2.5s",
        "EDA|TMP__q_0.9_abs_diff__w=5s_s=2.5s",
    ]
    assert set(res_df.columns.values) == set(expected_output_names)
    assert (res_df[expected_output_names[0]] != res_df[expected_output_names[1]]).any()
    assert (res_df[expected_output_names[0]] != res_df[expected_output_names[2]]).any()


### Test 'error' use-cases


def test_type_error_add_feature_collection(dummy_data):
    fd = FeatureDescriptor(
        function=np.sum,
        series_name="EDA",
        window="5s",
        stride="2.5s",
    )
    fc = FeatureCollection(feature_descriptors=fd)

    with pytest.raises(TypeError):
        fc.add(np.sum)


def test_one_to_many_error_feature_collection(dummy_data):
    def quantiles(sig: pd.Series) -> Tuple[float, float, float]:
        return np.quantile(sig, q=[0.1, 0.5, 0.9])

    # quantiles should be wrapped in a NumpyFuncWrapper
    fd = FeatureDescriptor(quantiles, series_name="EDA", window="5s", stride="2.5s")
    fc = FeatureCollection(fd)

    with pytest.raises(Exception):
        fc.calculate(dummy_data)


def test_one_to_many_wrong_np_funcwrapper_error_feature_collection(dummy_data):
    def quantiles(sig: pd.Series) -> Tuple[float, float, float]:
        return np.quantile(sig, q=[0.1, 0.5, 0.9])

    # Wrong number of output_names in func wrapper
    q_func = NumpyFuncWrapper(quantiles, output_names=["q_0.1", "q_0.5"])
    fd = FeatureDescriptor(q_func, series_name="EDA", window="5s", stride="2.5s")
    fc = FeatureCollection(fd)

    with pytest.raises(Exception):
        fc.calculate(dummy_data)


def test_one_to_many_error_feature_collection(dummy_data):
    def abs_mean_diff(sig1: pd.Series, sig2: pd.Series) -> float:
        # Note that this func only works when sig1 and sig2 have the same length
        return np.mean(np.abs(sig1 - sig2))

    # Give wrong nb of series names in tuple
    fd = FeatureDescriptor(
        abs_mean_diff, series_name=("EDA", "TMP", "ACC_x"), window="5s", stride="2.5s"
    )
    fc = FeatureCollection(fd)

    with pytest.raises(Exception):
        fc.calculate(dummy_data)