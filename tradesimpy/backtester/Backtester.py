import math as m
import numpy as np
import pandas as pd
import exceptions as ex
import logging as log
from BacktestResults import BacktestResults
from TradeDecision import TradeDecision
from TradeDecisions import TradeDecisions


class Backtester(object):

    def __init__(self, backtest_id, trading_algorithm, cash, commission, ticker_spreads):
        self.backtest_id = backtest_id
        self.trading_algorithm = trading_algorithm
        self.cash = cash
        self.commission = commission
        self.ticker_spreads = ticker_spreads
        self.open_share_price = {}
        self.purchased_shares = {}
        self.prev_cash_amount = self.cash
        self.prev_invested_amount = 0.0

    def run(self, data, start_date, end_date, cash=None):
        self.data = data

        # Handle missing cash value
        if cash is not None:
            self.cash = cash
        if self.cash is None:
            self.cash = 10000

        if(self.cash <= 0):
            raise ValueError("Cash must be greater than zero.")

        # Find the tradable date-times so as to include enough data to accommodate for history window
        datetimes = []
        for ticker in self.trading_algorithm.tickers:
            ticker_dates = self.data[ticker].index[self.trading_algorithm.history_window:]
            datetimes.extend(ticker_dates)
            log.info("Ticker %s will begin making trade decisions on %s" % (ticker, ticker_dates[0]))
        datetimes = sorted(list(set(datetimes)))

        # Intialize daily results structures
        self.portfolio_value = {}
        self.invested_amount = {}
        self.cash_amount = {}
        self.commissions = {}
        self.transactions = {}

        # Initialize simulation results helper variables
        algo_window_length = self.trading_algorithm.history_window
        self.trade_decision = TradeDecisions()
        self.purchased_shares = {}
        self.open_share_price = {}
        self.prev_cash_amount = self.cash
        self.prev_invested_amount = 0.0

        # Iterate over all tradable days
        for current_datetime in datetimes:
            self.cash_amount[current_datetime] = self.prev_cash_amount
            self.invested_amount[current_datetime] = self._mark_portfolio_to_market(current_datetime)
            self.commissions[current_datetime] = 0.0
            self.transactions[current_datetime] = {}

            if(not self.trade_decision.is_empty):
                # Execute sales first to be sure cash is available for potential purchases
                # Close positions
                for trade_decision in self.trade_decision.close:
                    self._execute_transaction(current_datetime, trade_decision)
                # Open positions
                for trade_decision in self.trade_decision.open:
                    self._execute_transaction(current_datetime, trade_decision)

            # Retrieve data needed for algorithm
            algorithm_data = {}
            for ticker in self.trading_algorithm.tickers:
                # Only include data for those tickers which can trade TODAY (i.e., existing present observation)
                if(current_datetime in self.data[ticker].index):
                    algorithm_data[ticker] = self.data[ticker][:current_datetime][-algo_window_length-1:]
                else:
                    log.warning("Date %s is not tradable for ticker %s" % (current_datetime, ticker))

            # Remember current asset amounts for next iteration
            self.prev_cash_amount = self.cash_amount[current_datetime]
            self.prev_invested_amount = self.invested_amount[current_datetime]

            # Determine trade decisions for tomorrow's open
            self.trade_decision = self.trading_algorithm.trade_decision(algorithm_data)

        # Close all open positions after finishing the backtest
        if len(self.purchased_shares) != 0:
            temp_purchased_shares = self.purchased_shares.copy()

            for ticker, share_count in temp_purchased_shares.iteritems():
                self._execute_transaction(current_datetime, TradeDecision(ticker, 'close', position_percent=1.0))

        # Save results
        self.results = BacktestResults(self.backtest_id, self.cash_amount, self.invested_amount, self.commissions, \
            self.transactions)

        return self.results

    def _execute_transaction(self, current_datetime, trade_decision):
        ticker = trade_decision.ticker
        ticker_idx = self.trading_algorithm.tickers.index(trade_decision.ticker)
        current_invested_amount = self._mark_portfolio_to_market(current_datetime)
        self.commissions[current_datetime] += self.commission

        if trade_decision.open_or_close == 'close':
            # Be sure there are purchased shares for the close request
            if(ticker in self.purchased_shares):
                # TODO: Allow user to sell portions of position, currently closes entire position.
                #       Should know number of shares currently owned per ticker before closing.
                #       Don't execute if number of shares owned doesn't equal those wishing to be closed.
                share_price = (1 - self.ticker_spreads[ticker_idx] / 2) * self.data[ticker].loc[current_datetime, 'Open']
                self.cash_amount[current_datetime] = self.prev_cash_amount + (self.purchased_shares[ticker] * share_price) \
                    - self.commission
                self.invested_amount[current_datetime] = current_invested_amount - (self.purchased_shares[ticker] * share_price)
                self.transactions[current_datetime][ticker] = {
                    'position': 0,
                    'share_count': self.purchased_shares[ticker],
                    'share_price': share_price
                }
                del self.purchased_shares[ticker]
        else:
            share_price = (1 + self.ticker_spreads[ticker_idx] / 2) * self.data[ticker].loc[current_datetime, 'Open']
            total_share_count = self._determine_share_count(self.cash_amount[current_datetime], share_price, \
                trade_decision.share_count, trade_decision.position_percent)

            # Prior to purchase, be sure enough cash is available
            if((share_price * total_share_count) > self.cash_amount[current_datetime]):
                log.warning("Cash amount %f is not enough to purchase shares at date-time %s" \
                    % (self.cash_amount[current_datetime], current_datetime))
                return

            # Open position
            self.open_share_price[ticker] = share_price
            self.purchased_shares[ticker] = total_share_count
            self.cash_amount[current_datetime] = self.prev_cash_amount - (self.purchased_shares[ticker] * share_price) \
                - self.commission
            self.invested_amount[current_datetime] = self.prev_invested_amount + (self.purchased_shares[ticker] \
                * self.data[ticker].loc[current_datetime, 'Close'])
            self.transactions[current_datetime][ticker] = {
                'position': 1,
                'share_count': self.purchased_shares[ticker],
                'share_price': share_price
            }

    def _mark_portfolio_to_market(self, current_datetime):
        if len(self.purchased_shares) != 0:
            invested_amount = 0
            temp_purchased_shares = self.purchased_shares.copy()

            # Determine current invested amount
            for ticker, share_count in temp_purchased_shares.iteritems():
                invested_amount += share_count * self.data[ticker].loc[current_datetime, 'Close']

            return invested_amount
        else:
            return 0.0

    def _determine_share_count(self, leftover_cash, share_price, share_count, position_percent):
        if share_count is not None:
            return share_count
        elif position_percent is not None:
            return m.floor((leftover_cash / share_price) * position_percent)
        else:
            raise ValueError('Both share_count and position_percent were None.')
