import numpy as np

class MockBinaryModel:
    def __init__(self, seed=None):
        self.rng = np.random.default_rng(seed)

    def predict_proba(self, X):
        """
        Return probabilities for class 0 and class 1 as an (n_samples, 2) array.
        """
        n_samples = self._get_n_samples(X)
        class_1_probs = self.rng.uniform(0.05, 0.95, size=n_samples)
        class_0_probs = 1 - class_1_probs
        return np.vstack([class_0_probs, class_1_probs]).T

    def predict(self, X, threshold=0.5):
        """
        Return binary class predictions (0 or 1).
        """
        proba = self.predict_proba(X)
        return (proba[:, 1] >= threshold).astype(int)

    def _get_n_samples(self, X):
        """
        Internal: determine the number of samples (rows) in X.
        """
        # Handles DataFrame, numpy array, list of dicts, list of lists/tuples, or single dict
        if hasattr(X, "shape"): 
            if X.ndim == 0: # Handles 0-d arrays if they sneak in
                return 1
            if X.ndim == 1 and isinstance(X, np.ndarray) and X.shape[0] > 0 and isinstance(X[0], (dict, list, tuple)):
                # Handles a 1D numpy array of objects (like dicts) - less common for direct model input but robust.
                return X.shape[0]
            if X.ndim == 1: # A 1D array of features for a single sample
                return 1
            return X.shape[0] # Number of rows for 2D+ arrays
        if isinstance(X, list): # Handles list of dicts or list of lists/tuples
            return len(X)
        # This case should ideally not be hit if input is wrapped in a list for single scoring
        if isinstance(X, dict):
            return 1
        raise TypeError(f"Unsupported input type for _get_n_samples: {type(X)}")

