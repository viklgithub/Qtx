import streamlit as st
import numpy as np
import pandas as pd
import asyncio
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from quotexapi.stable_api import Quotex
import talib

# Page config
st.set_page_config(page_title="MACD Trading Strategy", layout="wide")

class MACDStrategy:
    def __init__(self, client: Quotex, asset: str, amount: float = 50, duration: int = 60):
        self.client = client
        self.asset = asset
        self.amount = amount
        self.duration = duration
        self.ma_period = 200
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9

    async def get_historical_data(self, days=30):
        """Get historical candle data and calculate indicators"""
        offset = 3600
        period = 60
        
        timestamp = int(pd.Timestamp.now().timestamp()) - (days * 24 * 60 * 60)
        candles = await self.client.get_candles(self.asset, timestamp, offset, period)
        
        if not candles:
            return None
            
        df = pd.DataFrame(candles)
        df['close'] = pd.to_numeric(df['close'])
        df['high'] = pd.to_numeric(df['high'])
        df['low'] = pd.to_numeric(df['low'])
        df['open'] = pd.to_numeric(df['open'])
        df['timestamp'] = pd.to_datetime(df['time'], unit='s')
        
        # Calculate indicators
        df['ma200'] = talib.SMA(df['close'], timeperiod=self.ma_period)
        macd, signal, hist = talib.MACD(df['close'], 
                                      fastperiod=self.macd_fast,
                                      slowperiod=self.macd_slow,
                                      signalperiod=self.macd_signal)
        df['macd'] = macd
        df['signal'] = signal
        df['hist'] = hist
        
        return df

def plot_strategy(df):
    """Create interactive plot with Plotly"""
    fig = make_subplots(rows=2, cols=1, shared_xaxis=True, 
                       vertical_spacing=0.03, 
                       row_heights=[0.7, 0.3])

    # Candlestick chart
    fig.add_trace(go.Candlestick(
        x=df['timestamp'],
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='Price'
    ), row=1, col=1)

    # 200 MA
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['ma200'],
        name='200 MA',
        line=dict(color='orange')
    ), row=1, col=1)

    # MACD
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['macd'],
        name='MACD',
        line=dict(color='blue')
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['signal'],
        name='Signal',
        line=dict(color='orange')
    ), row=2, col=1)

    # MACD histogram
    colors = ['red' if x < 0 else 'green' for x in df['hist']]
    fig.add_trace(go.Bar(
        x=df['timestamp'],
        y=df['hist'],
        name='Histogram',
        marker_color=colors
    ), row=2, col=1)

    fig.update_layout(
        title='MACD Trading Strategy Analysis',
        xaxis_title='Date',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False
    )

    return fig

def main():
    st.title("MACD Trading Strategy Dashboard")
    
    # Sidebar for input parameters
    st.sidebar.header("Configuration")
    
    # Login credentials
    email = st.sidebar.text_input("Quotex Email", type="password")
    password = st.sidebar.text_input("Quotex Password", type="password")
    
    # Trading parameters
    asset = st.sidebar.selectbox(
        "Select Asset",
        ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "EURUSD_otc"]
    )
    
    amount = st.sidebar.number_input("Trade Amount", min_value=1, value=50)
    duration = st.sidebar.number_input("Trade Duration (seconds)", min_value=60, value=60, step=60)
    
    # Connect button
    if st.sidebar.button("Connect and Analyze"):
        if not email or not password:
            st.error("Please enter your Quotex credentials")
            return
            
        try:
            # Initialize client and strategy
            client = Quotex(email=email, password=password)
            strategy = MACDStrategy(client, asset, amount, duration)
            
            # Create placeholder for status
            status_placeholder = st.empty()
            status_placeholder.info("Connecting to Quotex...")
            
            # Get historical data
            async def get_data():
                check_connect, message = await client.connect()
                if check_connect:
                    return await strategy.get_historical_data()
                else:
                    return None
                    
            df = asyncio.run(get_data())
            
            if df is not None:
                status_placeholder.success("Connected! Analyzing data...")
                
                # Display current market conditions
                col1, col2, col3 = st.columns(3)
                with col1:
                    trend = "UPTREND" if df['close'].iloc[-1] > df['ma200'].iloc[-1] else "DOWNTREND"
                    st.metric("Trend", trend)
                with col2:
                    st.metric("Current Price", f"{df['close'].iloc[-1]:.5f}")
                with col3:
                    signal = "NONE"
                    if df['macd'].iloc[-1] > df['signal'].iloc[-1] and df['macd'].iloc[-2] <= df['signal'].iloc[-2]:
                        signal = "CALL" if df['macd'].iloc[-1] < 0 else "NONE"
                    elif df['macd'].iloc[-1] < df['signal'].iloc[-1] and df['macd'].iloc[-2] >= df['signal'].iloc[-2]:
                        signal = "PUT" if df['macd'].iloc[-1] > 0 else "NONE"
                    st.metric("Signal", signal)
                
                # Plot the chart
                fig = plot_strategy(df)
                st.plotly_chart(fig, use_container_width=True)
                
                # Trading controls
                if st.button("Place Trade"):
                    if signal != "NONE":
                        status_placeholder.info(f"Placing {signal} trade...")
                        async def place_trade():
                            return await strategy.execute_trade(signal)
                        
                        if asyncio.run(place_trade()):
                            status_placeholder.success("Trade executed successfully!")
                        else:
                            status_placeholder.error("Trade execution failed")
                    else:
                        st.warning("No valid trading signal at the moment")
                        
            else:
                status_placeholder.error("Failed to connect to Quotex")
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()
