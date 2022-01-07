# -*- coding: utf-8 -*-
from abc import ABC
from typing import Callable, Union

import numpy as np
from numpy.random import RandomState
from sklearn.utils import check_random_state

from sktime.clustering_redo.base import BaseClusterer
from sktime.distances import distance_factory, pairwise_distance
from sktime.transformations.base import BaseTransformer


def _numba_lloyds(
    X: np.ndarray, distance: Callable, initial_center_indexes: np.ndarray
):
    cluster_assignment_indexes = _assign_clusters(X, distance, initial_center_indexes)
    print(cluster_assignment_indexes)

    new_centers = _compute_new_cluster_centers(X, cluster_assignment_indexes)


def _assign_clusters(X: np.ndarray, distance: Callable, center_indexes: np.ndarray):
    """Assign each instance to a cluster.

    This is done by computing the distance between each instance and
    each cluster. For each instance an index is returned that indicates
    which center had the smallest distance to it.

    Returns
    -------
    np.ndarray (1d array of shape (n_instance,))
        Array of indexes of each instances closest cluster.
    """
    return pairwise_distance(X, X[center_indexes, :], metric=distance).argmin(axis=1)


def _compute_new_cluster_centers(X: np.ndarray, cluster_assignment_indexes: np.ndarray):
    pass


def _forgy_center_initializer(
    X: np.ndarray, n_centers: int, random_state: np.random.RandomState
):
    """Compute the initial centers using forgy method.

    Parameters
    ----------
    X : np.ndarray (2d or 3d array of shape (n_instances, series_length) or shape
        (n_instances,n_dimensions,series_length))
        Time series instances to cluster.
    n_clusters: int, defaults = 8
        The number of clusters to form as well as the number of
        centroids to generate.
    random_state: np.random.RandomState
        Determines random number generation for centroid initialization.

    Returns
    -------
    np.ndarray (1d array of shape (n_clusters,))
        Indexes of the cluster centers.
    """
    return random_state.choice(X.shape[0], n_centers)


class _Lloyds(BaseClusterer, BaseTransformer, ABC):
    """Abstact class that implement time series Lloyds algorithm.

    Parameters
    ----------
    n_clusters: int, defaults = 8
        The number of clusters to form as well as the number of
        centroids to generate.
    init_algorithm: str, defaults = 'forgy'
        Method for initializing cluster centers. TODO: Add specific strings
    metric: str or Callable, defaults = 'dtw'
        Distance metric to compute similarity between time series.
    n_init: int, defaults = 10
        Number of times the k-means algorithm will be run with different
        centroid seeds. The final result will be the best output of n_init
        consecutive runs in terms of inertia.
    max_iter: int, defaults = 30
        Maximum number of iterations of the k-means algorithm for a single
        run.
    tol: float, defaults = 1e-4
        Relative tolerance with regards to Frobenius norm of the difference
        in the cluster centers of two consecutive iterations to declare
        convergence.
    verbose: bool, defaults = False
        Verbosity mode.
    random_state: int or np.random.RandomState instance or None, defaults = None
        Determines random number generation for centroid initialization.

    Attributes
    ----------
    cluster_centers_: np.ndarray (3d array of shape (n_clusters, n_dimensions, series_length))
        Time series that represent each of the cluster centers. If the algorithm stops before
        fully converging these will not be consistent with labels_.
    labels_: np.ndarray (1d array of shape (n_instance,))
        Labels that is the index each time series belongs to.
    inertia_: float
        Sum of squared distances of samples to their closest cluster center, weighted by
        the sample weights if provided.
    n_iter_: int
        Number of iterations run.
    """

    _tags = {
        "coerce-X-to-numpy": True,
        "coerce-X-to-pandas": False,
        "capability:multivariate": True,
        "capability:unequal_length": False,
        "capability:missing_values": False,
        "capability:train_estimate": False,
        "capability:contractable": False,
        "capability:multithreading": False,
    }

    _init_algorithms = {"forgy": _forgy_center_initializer, "random": None}

    def __init__(
        self,
        n_clusters: int = 8,
        init_algorithm: Union[str, Callable] = "forgy",
        metric: Union[str, Callable] = "dtw",
        n_init: int = 10,
        max_iter: int = 300,
        tol: float = 1e-4,
        verbose: bool = False,
        random_state: Union[int, RandomState] = None,
    ):
        self.n_clusters = n_clusters
        self.init_algorithm = init_algorithm
        self.metric = metric
        self.n_init = n_init
        self.max_iter = max_iter
        self.tol = tol
        self.verbose = verbose
        self.random_state = random_state

        self.cluster_centers_ = None
        self.labels_ = None
        self.intertia_ = None
        self.n_iter = 0

        self._init_algorithm = None
        self._distance_metric = None
        self._random_state = None

        super(_Lloyds, self).__init__()

    def _check_params(self, X: np.ndarray) -> None:
        """Check parameters are valid and initialized.

        Parameters
        ----------
        X : np.ndarray (2d or 3d array of shape (n_instances, series_length) or shape
            (n_instances,n_dimensions,series_length))
            Time series instances to cluster.

        Raises
        ------
        ValueError
            If the init_algorithm value is invalid.
        """
        if self._random_state is None:
            self._random_state = check_random_state(self.random_state)

        self._distance_metric = distance_factory(X[0], X[1], metric=self.metric)

        if isinstance(self.init_algorithm, str):
            self._init_algorithm = self._init_algorithms.get(self.init_algorithm)
        else:
            self._init_algorithm = self.init_algorithm

        print(self._init_algorithms)
        print(self.init_algorithm)

        if not isinstance(self._init_algorithm, Callable):
            print(self._init_algorithm)
            raise ValueError(
                f"The value provided for init_algorim: {self.init_algorithm} is invalid. "
                f"The following are a list of valid init algorithms strings: "
                f"{list(self._init_algorithms.keys())}"
            )

    def _fit(self, X: np.ndarray, y=None) -> np.ndarray:
        """Fit time series clusterer to training data.

        Parameters
        ----------
        X : np.ndarray (2d or 3d array of shape (n_instances, series_length) or shape
            (n_instances,n_dimensions,series_length))
            Training time series instances to cluster.
        y: ignored, exists for API consistency reasons.

        Returns
        -------
        self:
            Fitted estimator.
        """
        self._check_params(X)
        self.cluster_centers_ = self._init_algorithm(
            X, self.n_clusters, self._random_state
        )
        _numba_lloyds(X, self._distance_metric, self.cluster_centers_)
        pass

    def _predict(self, X: np.ndarray, y=None) -> np.ndarray:
        """Predict the closest cluster each sample in X belongs to.

        Parameters
        ----------
        X : np.ndarray (2d or 3d array of shape (n_instances, series_length) or shape
            (n_instances,n_dimensions,series_length))
            Time series instances to predict their cluster indexes.
        y: ignored, exists for API consistency reasons.

        Returns
        -------
        np.ndarray (1d array of shape (n_instances,))
            Index of the cluster each time series in X belongs to.
        """
        pass