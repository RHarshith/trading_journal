import pandas as pd

## INPUTS FOR THE SCRIPT

# 1.
# Provide the file path for the zerodha report.
# Make sure to download the 'CSV' format of the tradebook.
# DO NOT download the P&L report or the Tax P&L report, it won't work.
zerodha_tradebook_filename = "tradebook-XXX999-EQ.csv"

# 2.
# Provide a list of dates that indicate the start date of each trading session.
# For example, if you are a swing trader who trades about 20 stocks every month as one trading session,
# Then your input would be ["2024-01-01", "2024-02-01", "2024-03-01",....]
# If you don't want to provide separate sessions, just give todays date as input
trading_sessions = ["2024-02-01"]



def metrics(df):
    res = {}
    res['win_rate'] = len(df[df['gain']>=0])/len(df)
    res['lose_rate'] = len(df[df['gain']<0])/len(df)
    res['avg_gain'] = df[df['gain']>=0]['gain'].mean()
    res['avg_loss'] = df[df['gain']<0]['gain'].mean()
    res['avg_gain_absolute'] = df[df['gain_pct']>0]['gain_pct'].mean()
    res['avg_loss_absolute'] = df[df['gain_pct']<0]['gain_pct'].mean()
    res['reward_risk_ratio'] = res['avg_gain']/(res['avg_loss']*-1)
    res['reward_risk_ratio_absolute'] = res['avg_gain_absolute']/res['avg_loss_absolute']*-1
    res['expectency'] = res['win_rate'] * res['reward_risk_ratio']/res['lose_rate']
    res['expectency_absolute'] = res['win_rate'] * res['reward_risk_ratio_absolute']/res['lose_rate']
    return pd.Series(res)

def metrics_per_symbol(df):
    df = df.sort_values('trade_date')
    symbol = df['symbol'].iloc[0]
    last_trade = {
        'symbol': symbol,
        'buy_price': 0,
        'sell_price': 0,
        'total_buy_price': 0,
        'total_sell_price': 0,
        'buy_quantity': 0,
        'sell_quantity': 0,
        'last_buy_date': None,
        'first_buy_date': None,
        'buy_dates': [],
        'first_sell_date': None,
        'last_sell_date': None,
        'sell_dates': [],
        'trade_type': None,
        'quantity_mismatch': False,
        'executed': False,
    }
    all_trades = []
    for _, row in df.iterrows():
        if row['trade_type'] == 'buy':
            last_trade['buy_price'] = (
                row['price']*row['quantity']+last_trade['buy_price']*last_trade['buy_quantity']
            )/(row['quantity']+last_trade['buy_quantity'])
            last_trade['buy_quantity'] += row['quantity']
            last_trade['total_buy_price'] = last_trade['buy_price']*last_trade['buy_quantity']
            last_trade['last_buy_date'] = row['trade_date']
            last_trade['buy_dates'].append(row['trade_date'])
            if last_trade['trade_type'] is None:
                last_trade['trade_type'] = 'long'
            if last_trade['first_buy_date'] is None:
                last_trade['first_buy_date'] = row['trade_date']
        else:
            last_trade['sell_price'] = (
                row['price']*row['quantity']+last_trade['sell_price']*last_trade['sell_quantity']
            )/(row['quantity']+last_trade['sell_quantity'])
            last_trade['sell_quantity'] += row['quantity']
            last_trade['total_sell_price'] = last_trade['sell_price']*last_trade['sell_quantity']
            last_trade['last_sell_date'] = row['trade_date']
            last_trade['sell_dates'].append(row['trade_date'])
            if last_trade['trade_type'] is None:
                last_trade['trade_type'] = 'short'
            if last_trade['first_sell_date'] is None:
                last_trade['first_sell_date'] = row['trade_date']

        if last_trade['buy_quantity'] == last_trade['sell_quantity']:
            last_trade['executed'] = True
            all_trades.append(last_trade)
            last_trade = {
                'symbol': symbol,
                'buy_price': 0,
                'sell_price': 0,
                'total_buy_price': 0,
                'total_sell_price': 0,
                'buy_quantity': 0,
                'sell_quantity': 0,
                'last_buy_date': None,
                'first_buy_date': None,
                'buy_dates': [],
                'first_sell_date': None,
                'last_sell_date': None,
                'sell_dates': [],
                'trade_type': None,
                'quantity_mismatch': False,
                'executed': False
            }

    if not all_trades:
        if last_trade['buy_quantity'] < last_trade['sell_quantity'] and last_trade['trade_type'] == 'long':
            last_trade['quantity_mismatch'] = True
        all_trades = [last_trade]
            
    res = pd.DataFrame(all_trades)
    res['gain'] = res['total_sell_price'] - res['total_buy_price']
    res['gain_pct'] = res['gain']*100/res['total_buy_price']
    res['winning_trade'] = res['gain'].apply(lambda x: x>=0)
    return res


if __name__ == "main":

    # Read the tradebook as input
    df = pd.read_csv(zerodha_tradebook_filename)

    # First, group all intraday buy trades, and intraday sell trades on the same stock. 
    gdf = df.groupby(
        ['symbol', 'trade_date', 'trade_type']
    ).agg({'quantity': 'sum', 'price': 'mean'}).reset_index()

    # Group all buy and sell trades to create one single trade for each stock
    symbol_df = pd.DataFrame()
    for _, session_df in gdf.groupby('symbol'):
        res = metrics_per_symbol(session_df)
        symbol_df = pd.concat([symbol_df, res])
    
    
    # Finally, for each trading session, calculate metrics like avg. gain and loss, hit rate,
    # risk:reward and expectancy
    # expectancy = win_ratio * reward:risk ratio / lose_ratio
    trading_session_metrics = []
    
    for dt in trading_sessions:
        temp_df = symbol_df[symbol_df['first_buy_date']<dt]
        analytics = metrics(temp_df[temp_df['executed'] == True])
        analytics['session_end'] = dt
        trading_sessions.append(analytics.to_dict())

    metrics_df = pd.DataFrame(trading_sessions)

    # Write the journal and the metrics to an excel sheet.
    with pd.ExcelWriter('tradebook.xlsx',engine="openpyxl") as writer:
        symbol_df.to_excel(writer,sheet_name='tradebook',index=False)
        metrics_df.to_excel(writer,sheet_name='reports',index=True)


