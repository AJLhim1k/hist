import mplfinance as mpf
import pandas as pd


def make_graph(p, mode):
    df = pd.read_csv(f'.\data_{mode}\data{p}.csv')
    df['date'] = pd.to_datetime(df['time'].str.replace('T', ' '), format='%Y-%m-%d %H:%M:%S')
    df.set_index('date', inplace=True)
    mc = mpf.make_marketcolors(
        up='#2dd242',
        down='red',
        wick='inherit',
        edge='inherit',
        volume='in'
    )
    s = mpf.make_mpf_style(
        marketcolors=mc,
        facecolor='white',
        edgecolor='black',
        gridcolor='lightgray',
        gridstyle='--'
    )
    fig, axes = mpf.plot(
        df,
        type='candle',
        volume=True,
        style=s,
        returnfig=True,
        tight_layout=True,
        ylabel='',
        ylabel_lower=''
    )
    axes[0].set_xticks([])
    axes[0].set_xticklabels([])
    axes[0].get_xaxis().set_visible(False)
    delimeter = '\\'
    if mode == 'q':
        fig.savefig(f'.{delimeter}questions{delimeter}plot{p}.png', bbox_inches='tight', )
    elif mode == 'ans':
        fig.savefig(f'.{delimeter}questions{delimeter}answers{delimeter}plot{p}.png', bbox_inches='tight', )

if __name__ == '__main__':
    for i in range(441, 521):
        make_graph(i, 'q')
