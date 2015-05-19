from simulator_import import *
import math as m
import numpy as np
import pandas as pd
from pprint import pprint


class Simulator(object):
    def __init__(self, capital_base, commission, tickers_spreads, stop_loss_percent, carry_over_trades=False,
                 trading_algo=None, data=None):
        self.trading_algo = trading_algo
        self.data = data
        self.capital_base = capital_base
        self.start_dates = dict()
        self.portfolio_global_high = capital_base
        self.portfolio_local_low = capital_base
        self.max_drawdown = 0.0
        self.carry_over_trades = carry_over_trades
        self.commission = commission
        self.tickers_spreads = tickers_spreads
        self.stop_loss_percent = stop_loss_percent

        self.open_share_price = dict()
        self.stop_losses = dict()
        self.purchased_shares = dict()
        self.prev_portfolio_value = self.capital_base
        self.prev_cash_amount = self.capital_base
        self.prev_invested_amount = 0.0

        if trading_algo is not None and data is not None:
            # Determine trading start dates for each ticker
            for ticker in self.trading_algo.tickers:
                self.start_dates[ticker] = data[ticker].iloc[self.trading_algo.hist_window].name

            # TODO: Make this more flexible for multiple tickers!
            self.dates =\
                data[self.trading_algo.tickers[0]][self.start_dates[self.trading_algo.tickers[0]]:].index.tolist()

    def run(self, capital_base=10000, trading_algo=None, data=None):
        self.capital_base = capital_base
        winning_trade_cnt = 0
        losing_trade_cnt = 0
        winning_trade_returns = list()
        losing_trade_returns = list()

        # Create trading algorithm if necessary
        if trading_algo is not None:
            self.trading_algo = trading_algo

        # Load data if necessary
        if data is not None:
            self.data = data

            # Determine trading start dates for each ticker
            for ticker in self.trading_algo.tickers:
                self.start_dates[ticker] = data[ticker].iloc[self.trading_algo.hist_window].name

            # TODO: Make this more flexible for multiple tickers!
            self.dates =\
                data[self.trading_algo.tickers[0]][self.start_dates[self.trading_algo.tickers[0]]:].index.tolist()

        # Intialize daily results structures
        portfolio_value = dict()
        p_n_l = dict()
        returns = dict()
        transactions = dict()
        invested_amount = dict()
        cash_amount = dict()
        commissions = dict()

        # Initialize simulation results helper variables
        algo_window_length = self.trading_algo.hist_window
        algo_data = dict()

        # Reset previous values if no trades should be carried over
        if not self.carry_over_trades:
            self.stop_losses = dict()
            self.purchased_shares = dict()
            self.prev_portfolio_value = self.capital_base
            self.prev_cash_amount = self.capital_base
            self.prev_invested_amount = 0.0
            self.open_share_price = dict()

        # Iterate over all trading days
        for date in self.dates:
            cash_amount[date] = 0.0
            invested_amount[date] = 0.0
            commissions[date] = 0.0
            transactions[date] = dict()

            for ticker in self.trading_algo.tickers:
                algo_data[ticker] = self.data[ticker][:date][-algo_window_length-1:-1]

            # Determine the trade decision for entire portfolio
            trade_desc = self.trading_algo.determine_trade_decision(algo_data)

            # Trade off of all trade decisions
            if len(trade_desc) != 0:
                for key, value in trade_desc.iteritems():
                    if value['position'] == 0 and key in self.purchased_shares.keys():  # Close existing position
                        # Mark the portfolio to market
                        current_invested_amount = 0.0
                        for k, v in self.purchased_shares.iteritems():
                            current_invested_amount += v*self.data[k].loc[date, 'Open']

                        # Determine at which share price to sell
                        # TODO: Introduce slippage here, set from config file
                        share_price = (1 - self.tickers_spreads[key]/2) * self.data[key].loc[date, 'Open']

                        # Record commission
                        commissions[date] += self.commission

                        # Sell shares for cash
                        cash_amount[date] =\
                            self.prev_cash_amount + self.purchased_shares[key]*share_price - self.commission

                        # End of day invested amount
                        invested_amount[date] = current_invested_amount - self.purchased_shares[key]*share_price

                        # Record transaction
                        transactions[date][key] = {
                            'position': 0,
                            'share_count': self.purchased_shares[key],
                            'share_price': share_price
                        }

                        # Wining or losing trade
                        if share_price > self.open_share_price[key]:
                            winning_trade_cnt += 1
                            winning_trade_returns.append((share_price / self.open_share_price[key]) - 1)
                        else:
                            losing_trade_cnt += 1
                            losing_trade_returns.append((share_price / self.open_share_price[key]) - 1)

                        # Remove purchased record and potential stop losses
                        del self.purchased_shares[key]
                        if self.stop_loss_percent != 0:
                            del self.stop_losses[key]

                    elif value['position'] == 1 and key not in self.purchased_shares.keys():  # Open long position
                        # Determine at which share price to buy
                        # TODO: Introduce slippage here, set from config file
                        share_price = (1 + self.tickers_spreads[key]/2) * self.data[key].loc[date, 'Open']
                        self.purchased_shares[key] =\
                            m.floor(self.prev_portfolio_value/share_price*value['portfolio_perc'])

                        # Record commission
                        commissions[date] += self.commission

                        # Purchase shares using cash
                        cash_amount[date] =\
                            self.prev_cash_amount - self.purchased_shares[key]*share_price - self.commission

                        # End of day invested amount
                        invested_amount[date] =\
                            self.prev_invested_amount + self.purchased_shares[key]*self.data[key].loc[date, 'Close']

                        # Record transaction
                        transactions[date][key] = {
                            'position': 1,
                            'share_count': self.purchased_shares[key],
                            'share_price': share_price
                        }
                        self.open_share_price[key] = share_price

                        # Set stop loss or trigger (if necessary)
                        if self.stop_loss_percent != 0:
                            stop_loss = share_price * (1 - self.stop_loss_percent)

                            # Trigger stop loss (if necessary)
                            if stop_loss >= self.data[key].loc[date, 'Low']:  # Close recently opened position
                                # Mark the portfolio to market
                                current_invested_amount = 0.0
                                for k, v in self.purchased_shares.iteritems():
                                    if key == k:
                                        current_invested_amount += v*stop_loss
                                    else:
                                        current_invested_amount += v*self.data[k].loc[date, 'Close']

                                # Record commission
                                commissions[date] += self.commission

                                # Sell shares for cash
                                cash_amount[date] += self.purchased_shares[key]*stop_loss - self.commission

                                # End of day invested amount
                                invested_amount[date] = current_invested_amount - self.purchased_shares[key]*stop_loss

                                # Record transaction
                                # TODO: Append to list to accomodate for multiple daily transactions
                                transactions[date][key] = {
                                    'position': 0,
                                    'share_count': self.purchased_shares[key],
                                    'share_price': stop_loss
                                }

                                # Wining or losing trade (should always be a loss)
                                if stop_loss > self.open_share_price[key]:
                                    winning_trade_cnt += 1
                                    winning_trade_returns.append((stop_loss / self.open_share_price[key]) - 1)
                                else:
                                    losing_trade_cnt += 1
                                    losing_trade_returns.append((stop_loss / self.open_share_price[key]) - 1)

                                # Remove purchased record
                                del self.purchased_shares[key]
                            else:
                                self.stop_losses[key] = stop_loss

                    # TODO: Allow for short selling
                    elif value['position'] == -1:  # Open short position
                        pass
                        # # Determine how many shares to purchase
                        # # TODO: Introduce slippage here, set from config file
                        # share_price = (1 - self.bid_ask_spread[key]/2) * self.data[key].loc[date, 'Open']
                        # purchased_shares[key] = -m.floor(prev_portfolio_value/share_price*value['portfolio_perc'])
                        #
                        # # Record commission
                        # commissions[date] += self.commission
                        #
                        # # Purchase shares using cash
                        # cash_amount[date] = prev_cash_amount - purchased_shares[key]*share_price - self.commission
                        #
                        # # End of day invested amount
                        # invested_amount[date] =\
                        #     prev_invested_amount + purchased_shares[key]*self.data[key].loc[date, 'Close']
                        #
                        # # Record transaction
                        # transactions[date][key] = {
                        #     'position': -1,
                        #     'share_count': purchased_shares[key],
                        #     'share_price': share_price
                        # }
                    else:  # No trades, check for triggered stop losses and mark portfolio to market
                        cash_amount[date] = self.prev_cash_amount

                        if len(self.purchased_shares) != 0:
                            temp_purchased_shares = self.purchased_shares.copy()

                            # Determine current invested amount
                            for key, value in temp_purchased_shares.iteritems():
                                # Check potential triggered stop-losses for open orders
                                if self.stop_loss_percent != 0:
                                    stop_loss = self.stop_losses[key]

                                    # TODO: Have this work for short positions too
                                    if stop_loss >= self.data[key].loc[date, 'Low']:
                                        # Mark the portfolio to market
                                        current_invested_amount = 0.0
                                        for k, v in self.purchased_shares.iteritems():
                                            if key == k:
                                                current_invested_amount += v*stop_loss
                                            else:
                                                current_invested_amount += v*self.data[k].loc[date, 'Close']

                                        # Record commission
                                        commissions[date] += self.commission

                                        # Sell shares for cash
                                        cash_amount[date] += value*stop_loss - self.commission

                                        # End of day invested amount
                                        invested_amount[date] = current_invested_amount - value*stop_loss

                                        # Record transaction
                                        # TODO: Append to list to accomodate for multiple daily transactions
                                        transactions[date][key] = {
                                            'position': 0,
                                            'share_count': value,
                                            'share_price': stop_loss
                                        }

                                        # Wining or losing trade (should always be a loss)
                                        if stop_loss > self.open_share_price[key]:
                                            winning_trade_cnt += 1
                                            winning_trade_returns.append((stop_loss / self.open_share_price[key]) - 1)
                                        else:
                                            losing_trade_cnt += 1
                                            losing_trade_returns.append((stop_loss / self.open_share_price[key]) - 1)

                                        # Remove purchased record
                                        del self.purchased_shares[key]
                                    else:
                                        invested_amount[date] += value*self.data[key].loc[date, 'Close']
                                else:
                                    invested_amount[date] += value*self.data[key].loc[date, 'Close']
            else:  # No trades, check for triggered stop losses and mark portfolio to market
                cash_amount[date] = self.prev_cash_amount

                if len(self.purchased_shares) != 0:
                    temp_purchased_shares = self.purchased_shares.copy()

                    # Determine current invested amount
                    for key, value in temp_purchased_shares.iteritems():
                        # Check potential triggered stop-losses for open orders
                        if self.stop_loss_percent != 0:
                            stop_loss = self.stop_losses[key]

                            # TODO: Have this work for short positions too
                            if stop_loss >= self.data[key].loc[date, 'Low']:
                                # Mark the portfolio to market
                                current_invested_amount = 0.0
                                for k, v in self.purchased_shares.iteritems():
                                    if key == k:
                                        current_invested_amount += v*stop_loss
                                    else:
                                        current_invested_amount += v*self.data[k].loc[date, 'Close']

                                # Record commission
                                commissions[date] += self.commission

                                # Sell shares for cash
                                cash_amount[date] += value*stop_loss - self.commission

                                # End of day invested amount
                                invested_amount[date] = current_invested_amount - value*stop_loss

                                # Record transaction
                                # TODO: Append to list to accomodate for multiple daily transactions
                                transactions[date][key] = {
                                    'position': 0,
                                    'share_count': value,
                                    'share_price': stop_loss
                                }

                                # Wining or losing trade (should always be a loss)
                                if stop_loss > self.open_share_price[key]:
                                    winning_trade_cnt += 1
                                    winning_trade_returns.append((stop_loss / self.open_share_price[key]) - 1)
                                else:
                                    losing_trade_cnt += 1
                                    losing_trade_returns.append((stop_loss / self.open_share_price[key]) - 1)

                                # Remove purchased record
                                del self.purchased_shares[key]
                            else:
                                invested_amount[date] += value*self.data[key].loc[date, 'Close']
                        else:
                            invested_amount[date] += value*self.data[key].loc[date, 'Close']

            # Record more trade stats
            portfolio_value[date] = cash_amount[date] + invested_amount[date]
            p_n_l[date] = portfolio_value[date] - self.prev_portfolio_value
            returns[date] = (portfolio_value[date] / self.prev_portfolio_value) - 1.0

            # Remember current asset amounts for next iteration
            self.prev_cash_amount = cash_amount[date]
            self.prev_invested_amount = invested_amount[date]
            self.prev_portfolio_value = portfolio_value[date]

            # Monitor portfolio drawdown (conservatively)
            if len(self.purchased_shares) != 0:
                # Price entire portfolio's day high and low
                portfolio_high = cash_amount[date]
                portfolio_low = cash_amount[date]
                for key, value in self.purchased_shares.iteritems():
                    portfolio_high += value*self.data[key].loc[date, 'High']
                    portfolio_low += value*self.data[key].loc[date, 'Low']

                if portfolio_high > self.portfolio_global_high:
                    self.portfolio_global_high = portfolio_high
                    self.portfolio_local_low = self.portfolio_global_high
                elif portfolio_low < self.portfolio_local_low:
                    self.portfolio_local_low = portfolio_low

                    # Record max drawdown
                    if ((self.portfolio_local_low / self.portfolio_global_high) - 1) < self.max_drawdown:
                        self.max_drawdown = (self.portfolio_local_low / self.portfolio_global_high) - 1

        # Determine if all open positions should be closed
        if not self.carry_over_trades:
            # Close all open positions that exist
            if len(self.purchased_shares) != 0:
                temp_purchased_shares = self.purchased_shares.copy()

                for key, value in temp_purchased_shares.iteritems():
                    # Mark the portfolio to market
                    current_invested_amount = 0.0
                    for k, v in self.purchased_shares.iteritems():
                        current_invested_amount += v*self.data[k].loc[date, 'Open']

                    # Determine at which share price to sell
                    # TODO: Introduce slippage here, set from config file
                    share_price = (1 - self.tickers_spreads[key]/2) * self.data[key].loc[date, 'Open']

                    # Record commission
                    commissions[date] += self.commission

                    # Sell shares for cash
                    cash_amount[date] = self.prev_cash_amount + self.purchased_shares[key]*share_price - self.commission

                    # End of day invested amount
                    invested_amount[date] = current_invested_amount - self.purchased_shares[key]*share_price

                    # Record transaction
                    transactions[date][key] = {
                        'position': 0,
                        'share_count': self.purchased_shares[key],
                        'share_price': share_price
                    }

                    # Remove purchased record
                    del self.purchased_shares[key]

        # Create data frame out of daily trade stats
        daily_results = pd.DataFrame(portfolio_value.values(), columns=['Portfolio Value'], index=portfolio_value.keys())
        daily_results['Cash'] = pd.Series(cash_amount.values(), index=cash_amount.keys())
        daily_results['Invested'] = pd.Series(invested_amount.values(), index=invested_amount.keys())
        daily_results['PnL'] = pd.Series(p_n_l.values(), index=p_n_l.keys())
        daily_results['Return'] = pd.Series(returns.values(), index=returns.keys())
        daily_results['Commission'] = pd.Series(commissions.values(), index=commissions.keys())
        daily_results['Transactions'] = pd.Series(transactions.values(), index=transactions.keys())
        daily_results = daily_results.sort_index()

        # Compute period statistics
        annual_avg_return = daily_results['Return'].mean() * 252
        annual_std_dev = daily_results['Return'].std() * np.sqrt(252)
        annual_semi_std_dev = daily_results['Return'].where(daily_results['Return'] < 0.0).std() * np.sqrt(252)
        years_traded = (((self.dates[-1] - self.dates[0]).days + 1) / 365.0)
        total_return = daily_results['Portfolio Value'][-1] / daily_results['Portfolio Value'][0]
        cagr = total_return ** (1 / years_traded) - 1
        sortino_ratio = float('NaN') if annual_semi_std_dev == 0 else annual_avg_return / annual_semi_std_dev
        mar_ratio = float('NaN') if self.max_drawdown == 0 else -cagr / self.max_drawdown

        # Create dictionary out of period stats
        period_results = {
            'Max Drawdown': -self.max_drawdown,
            'Sharpe Ratio': annual_avg_return / annual_std_dev,
            'Sortino Ratio': sortino_ratio,
            'MAR Ratio': mar_ratio,
            # 'Information Ratio': 0.0,
            'CAGR': cagr,
            'Total Return': total_return - 1,
            'Annual Return': annual_avg_return,
            'Annual Volatility': annual_std_dev,
            'Start Portfolio Value': daily_results['Portfolio Value'][0],
            'End Portfolio Value': daily_results['Portfolio Value'][-1],
            'Total Trades': daily_results['Transactions'].where(daily_results['Transactions'] != {}).count() / 2,
            'Winning Trades': winning_trade_cnt,
            'Losing Trades': losing_trade_cnt,
            'Average Winning Trade': float('NaN') if len(winning_trade_returns) == 0 else np.mean(winning_trade_returns),
            'Average Losing Trade': float('NaN') if len(losing_trade_returns) == 0 else np.mean(losing_trade_returns),
        }

        return period_results, daily_results
