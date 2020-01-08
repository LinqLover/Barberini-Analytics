#!/bin/bash
LOG=/var/log/bp-logs/daily.log
BASEDIR=$(dirname "$0")/..
{
echo "================================================================================================"
PATH=/usr/local/bin:$PATH
echo [$(date +"%Y-%m-%d %H:%M")]
make -C $BASEDIR startup
docker-compose -f $BASEDIR/docker-compose.yml exec -T luigi /bin/sh -c 'cd /app && make luigi-ui && sleep 5 && make luigi && make luigi-clean'
make -C $BASEDIR db-backup
make -C $BASEDIR shutdown
echo "================================================================================================"
} >> $LOG 2>&1

