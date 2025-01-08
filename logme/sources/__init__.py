#import sources.ATimeLogger
#import sources.Duolingo
#import sources.KoreaderClipping
#import sources.KoreaderStatistics

from .ATimeLogger import get_ProcessATimeLoggerApi, ATimeLoggerApi, ProcessATimeLoggerApi
from .Duolingo import DuolingoApi
from .KoreaderClipping import KoreaderClippingIngest
from .KoreaderStatistics import KoreaderStatistics, KoreaderDatabaseHandler