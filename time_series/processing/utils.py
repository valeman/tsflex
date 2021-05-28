# -*- coding: utf-8 -*-
"""Utilities for the processing pipelines."""

__author__ = "Jonas Van Der Donckt, Jeroen Van Der Donckt"

import os
import traceback
from typing import Dict, List, Any, Optional

import pandas as pd
from pathos.multiprocessing import ProcessPool
from tqdm.auto import tqdm

from .series_processor import SeriesProcessorPipeline


def process_chunks_multithreaded(
    df_dict_list: List[Dict[str, pd.DataFrame]],
    processing_pipeline: SeriesProcessorPipeline,
    show_progress: Optional[bool] = True,
    n_jobs:  Optional[int] = None,
    **processing_kwargs,
) -> List[Any]:
    """Process `df_dict_list` in a multithreaded manner, order is preserved.

    Note
    ----
    This method is not concerned with joining the chunks as this operation is highly
    dependent on the preprocessing steps. This is the user's responsibility.

    Parameters
    ----------
    df_dict_list: List[Dict[str, pd.DataFrame]]
        A list of df_dict chunks, most likely the output of `chunk_df_dict`.
    processing_pipeline: SeriesProcessorPipeline
        The pipeline that will be called on each item in `df_dict_list`.
    show_progress: bool, optional
        If True, the progress will be shown with a progressbar, by default True.
    n_jobs: int, optional
        The number of processes used for the chunked series processing. If `None`, then
        the number returned by `os.cpu_count()` is used, by default None.
    **processing_kwargs
        Keyword args that will be passed on to the processing pipeline.

    Returns
    -------
    List[Any]
        A list of the `processing_pipeline`'s outputs. The order is preserved.

    Note
    ----
    If any error occurs while executing the `processing_pipeline` on one of the chunks
    in `df_dict_list`, the traceback is printed and an empty dataframe is returned.
    We chose for this behavior, because in this way the other parallel processes are
    not halted in case of an error.

    """
    if n_jobs is None:
        n_jobs = os.cpu_count()

    def _executor(chunk):
        try:
            return processing_pipeline(list(chunk.values()), **processing_kwargs)
        except Exception:
            # Print traceback and return empty `pd.DataFrame` in order to not break the
            # other parallel processes.
            traceback.print_exc()
            return pd.DataFrame()

    processed_out = []
    with ProcessPool(nodes=min(n_jobs, len(df_dict_list)), source=True) as pool:
        results = pool.imap(_executor, df_dict_list)
        if show_progress:
            results = tqdm(results, total=len(df_dict_list))
        for f in results:
            processed_out.append(f)
        # Close & join because: https://github.com/uqfoundation/pathos/issues/131
        pool.close()
        pool.join()
        # Clear because: https://github.com/uqfoundation/pathos/issues/111
        pool.clear()
    return processed_out
