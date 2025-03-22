#!/bin/bash
docker build -t bitdruid/pywaybackup:latest .
docker run --name pywaybackup -v ".waybackup_snapshots:/waybackup_snapshots" bitdruid/pywaybackup:latest