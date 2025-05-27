#!/bin/bash
echo "root:${SSH_PASSWORD}" | chpasswd
exec /sbin/init
