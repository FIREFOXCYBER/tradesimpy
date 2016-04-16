import os
import sys

# Provide directory paths for necessary imports
lib_paths =\
    [
        os.path.abspath('../'),
        os.path.abspath('../data/'),
        os.path.abspath('../backtester/'),
        os.path.abspath('../optimizers/'),
        os.path.abspath('../trading_algorithms/'),
        os.path.abspath('../configurations/')
    ]

for lib_path in lib_paths:
    sys.path.append(lib_path)

sys.path = list(set(sys.path))
