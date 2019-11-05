#!/usr/bin/env python3.6
from bot import Bot
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Matrix bot')
    parser.add_argument('--loglevel', '-l', action='store',
                        choices=['DEBUG', 'INFO',
                                 'WARNING', 'ERROR', 'CRITICAL'],
                        default='CRITICAL',
                        help='Set logging level')
    args = parser.parse_args()

    bot = Bot(loglevel=args.loglevel)
    bot.serve()
