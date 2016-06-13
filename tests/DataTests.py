from tests_import import *
import pandas as pd
import unittest
import data_source_factory as dsf
from DataSource import DataSource
from QuandlDataSource import QuandlDataSource
from CSVDataSource import CSVDataSource


class DataTests(unittest.TestCase):
    def setUp(self):
        observations = {
            pd.to_datetime('2015-12-29'): 0.25,
            pd.to_datetime('2015-12-30'): 0.5,
            pd.to_datetime('2015-12-31'): 0.4,
            pd.to_datetime('2016-01-01'): 0.3,
            pd.to_datetime('2016-01-04'): 0.45,
            pd.to_datetime('2016-01-05'): 0.9,
            pd.to_datetime('2016-01-06'): 0.6,
            pd.to_datetime('2016-01-07'): 1.0,
            pd.to_datetime('2016-01-08'): 1.5,
            pd.to_datetime('2016-01-11'): 1.2,
        }
        self.test_series = pd.Series(observations)

    def test_create_quandl_data_source(self):
        ds = dsf.create_data_source('Quandl')
        
        # Check results
        self.assertIs(type(ds), QuandlDataSource)

    def test_create_csv_data_source(self):
        ds = dsf.create_data_source('CSV')
        
        # Check results
        self.assertIs(type(ds), CSVDataSource)

    def test_create_unknown_data_source(self):
        with self.assertRaises(NotImplementedError):
        	ds = dsf.create_data_source('junk')

    def test_quandl_data_source_column_to_ticker_series(self):
        column_name = 'YAHOO/SPY - Adjusted Close'
        ticker_name = 'SPY'
        series_name = 'Adjusted Close'
        tn, sn = QuandlDataSource().column_name_to_ticker_series_name(column_name)

        # Check results
        self.assertEqual(ticker_name, tn)
        self.assertEqual(series_name, sn)

    def test_create_multiple_with_known_data_sources(self):
        ds = dsf.create_data_sources(['Quandl', 'Quandl', 'CSV'])

        # Check results
        self.assertEqual(len(ds), 2)
        self.assertIs(type(ds['Quandl']), QuandlDataSource)
        self.assertIs(type(ds['CSV']), CSVDataSource)

    def test_create_multiple_with_unknown_data_sources(self):
		with self.assertRaises(NotImplementedError):
			ds = dsf.create_data_sources(['Quandl', 'CSV', 'junk'])

    def test_trim_time_series_with_existing_bording_dates(self):
        # Setup test object
        start_date = pd.to_datetime('2015-12-31')
        end_date = pd.to_datetime('2016-01-06')
        trimed_series = DataSource('test').trim_series_observations(self.test_series, 'dummy ticker', \
            'dummy series name', start_date, end_date, 0)

        # Check results
        self.assertEqual(trimed_series.index[0], start_date)
        self.assertEqual(trimed_series.index[-1], end_date)

    def test_trim_time_series_with_existing_bording_dates_and_history_window(self):
        # Setup test object
        start_date = pd.to_datetime('2015-12-31')
        end_date = pd.to_datetime('2016-01-06')
        trimed_series = DataSource('test').trim_series_observations(self.test_series, 'dummy ticker', \
            'dummy series name', start_date, end_date, 1)

        # Check results
        self.assertEqual(trimed_series.index[0], pd.to_datetime('2015-12-30'))
        self.assertEqual(trimed_series.index[-1], end_date)

    def test_trim_time_series_with_missing_start_date(self):
        # Setup test object
        start_date = pd.to_datetime('2015-12-01')
        end_date = pd.to_datetime('2016-01-06')
        trimed_series = DataSource('test').trim_series_observations(self.test_series, 'dummy ticker', \
            'dummy series name', start_date, end_date, 0)

        # Check results
        self.assertEqual(trimed_series.index[0], self.test_series.index[0])
        self.assertEqual(trimed_series.index[-1], end_date)

    def test_trim_time_series_with_missing_start_date_and_history_window(self):
        start_date = pd.to_datetime('2015-12-01')
        end_date = pd.to_datetime('2016-01-06')
        with self.assertRaises(IndexError):
            trimed_series = DataSource('test').trim_series_observations(self.test_series, 'dummy ticker', \
                'dummy series name', start_date, end_date, 1)

    def test_trim_time_series_with_missing_end_date(self):
        # Setup test object
        start_date = pd.to_datetime('2015-12-31')
        end_date = pd.to_datetime('2016-01-31')
        trimed_series = DataSource('test').trim_series_observations(self.test_series, 'dummy ticker', \
            'dummy series name', start_date, end_date, 0)

        # Check results
        self.assertEqual(trimed_series.index[0], start_date)
        self.assertEqual(trimed_series.index[-1], self.test_series.index[-1])

    def test_trim_time_series_with_missing_start_and_end_date(self):
        # Setup test object
        start_date = pd.to_datetime('2015-12-01')
        end_date = pd.to_datetime('2016-01-31')
        trimed_series = DataSource('test').trim_series_observations(self.test_series, 'dummy ticker', \
            'dummy series name', start_date, end_date, 0)

        # Check results
        self.assertEqual(trimed_series.index[0], self.test_series.index[0])
        self.assertEqual(trimed_series.index[-1], self.test_series.index[-1])

if __name__ == '__main__':
    unittest.main()
