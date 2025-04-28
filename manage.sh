#!/bin/bash
docker-compose exec oktools bash -c "OKTOOLS_CONFIG_FILE=docker.cfg python manage.py $@"
