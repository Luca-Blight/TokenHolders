# DE-Challenge

## Overview

This a simple API and pipeline that allows you to load and query on-chain transfer data associated with doge token holders.

[Here's a quick overview of the project](https://www.notion.so/Tessera-Test-bc360c1fdaae49c78dfa80687f4f1217?pvs=4_)

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
