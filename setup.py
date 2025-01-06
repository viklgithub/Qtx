from setuptools import setup

setup(
    name="macd-strategy-app",
    version="0.1.0",
    packages=["quotexapi"],
    install_requires=[
        "streamlit",
        "numpy",
        "pandas",
        "plotly",
        "TA-Lib",
    ],
)
