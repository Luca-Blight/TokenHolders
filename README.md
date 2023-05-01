# Token Holders API & Pipeline

## Overview

This a simple API and pipeline that allows you to load and query on-chain transfer data associated with doge token holders.

[Here's a quick overview of the project](https://evergreen-haircut-085.notion.site/bc360c1fdaae49c78dfa80687f4f1217?v=cfd5de9304de4010b205af078e62f306)

## API

http://3.82.117.210:8000/

### Endpoints

/token_holders
query params: limit:int, order_by:asc/desc

/token_holders/{address}
query params: balance:bool, weekly_balance_change:bool

## Local Setup

Install Packages Requisite Packages

```bash

pip install -r requirements.txt

```

Run the API and Indexer

```bash

sh entrypoints.sh

```

## Directory

```bash

├── README.md
├── app
│   ├── database
│   │   └── main.py
│   ├── indexers
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── models
│   │   └── TokenHolder.py
│   └── server
│       ├── Dockerfile
│       ├── main.py
│       └── requirements.txt
├── config
│   └── settings.py
├── docker-compose.yml
├── requirements.txt
└── tests
    ├── test_api.py
    └── test_indexer.py



```
