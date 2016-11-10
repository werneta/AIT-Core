#!/usr/bin/env python

'''
Usage:
    bliss_create_dirs.py [options]

Arguments:
    -c FILE, --config=<filename>    YAML config file, secondary to the
                                    BLISS_CONFIG, that contains a dictionary
                                    of path-related variables and applicable
                                    values.

    -d DAYS, --days=<days>  Number of days in advance of today's
                            date to create the directory structure.
                            Dependent on DDD or YYYY being specified in
                            configuration.

                            i.e. If today is 09/01/2016, and days=1, then this
                            script will create directories for tomorrow,
                            09/02/2016. [default: 0]

    -l LENGTH, --length=<days>  Number of days of directories to create
                                [default: 1]

    -v, --verbose   Verbose output [default: False]

Description:

    BLISS Create Directory Structure

    Based on the data paths specified in the BLISS_CONFIG, this software creates
    daily directories for the GDS based on the paths and any applicable variable
    substitution.

    Define the Paths
    ================

    Paths should be specified within the 'data' portion of the BLISS_CONFIG. It
    should follow the following hierarchy within the YAML file:

        data:
            data-type:
                path:

    For example:

        data:
            type_a:
                path: /path/to/data/type_a
            type_b:
                path: /path/to/data/type_b

    Be sure to use 'path' to specify the data path so the software knows to
    translate these paths as needed. You can use absolute or relative paths:

        data:
            type_a:
                path: to/data/type_a
            type_b:
                path: ~/to/data/type_b


    Variable Substitution
    =====================

    Variable substituion is also possible using any of the default-, platform-,
    or host- level attributes within the BLISS_CONFIG. To include a variable
    in a path use the following syntax, `${variable}`

    For example,

        default:
            mission: 'oco3'
            phase: 'int'

            data:
                type_a:
                    path: /${mission}/${phase}/data/type_a
                type_b:
                    path: /${mission}/${phase}/data/type_b

    Will create the directories:

        /oco3/int/data/type_a
        /oco3/int/data/type_b


    Special Variables
    =================

    There are also several special variables available:
    * year     = 4-digit year
    * doy      = 3-digit day-of-year
    * hostname = current machine hostname
    * platform = platform of the current machine (darwin, win32, etc.)

    For example,

        default:
            mission: 'oco3'
            phase: 'int'

            data:
                type_a:
                    path: /${mission}/${phase}/${year}/${doy}/type_a
                type_b:
                    path: /${mission}/${phase}/${year}/${doy}/type_b

    Will produce paths like (depending on the date):

        /oco3/int/2016/299/type_a
        /oco3/int/2016/299/type_b


    Additional Config File
    ======================

    Specified using the -c or --config command-line flags, this YAML file
    will contain variables that will be used for path substitution when
    creating the data directories. This will take precedence over any other
    values specified in BLISS_CONFIG or other defaults.

    Example YAML, BLISS_CONFIG path, and output directories:

    YAML:

        phase: 'ops'
        hostname: ['gds1', 'gds2', 'gds3']

    BLISS_CONFIG path:

        data:
            science: /${phase}/${hostname}/science

    Output Directories:

        /ops/gds1/science
        /ops/gds2/science
        /ops/gds3/science


    Multi-Day Directories
    =====================

    Using these date variables along with the DAYS (-d) and LENGTH (-l) flags
    from this software will allow you to manipulate the timeframes you would
    like to create directories for.


    Example Runs
    ============

    Create directories based on some set of variables in a separate YAML config

        $ bliss-create-dirs -c vars.yaml

    Create directories starting 3 days from now for 90 days

        $ bliss-create-dirs -d 3 -l 90

'''

from docopt import docopt
import bliss
import os
import errno
import yaml

def createDirStruct(paths, verbose=False):
    '''Loops bliss.config._datapaths from BLISS_CONFIG and creates a directory.

    Replaces YYYY and DDD with the respective year and day-of-year.
    If neither are given as arguments, current UTC day and year are used.

    Args:
        paths:
            [optional] list of directory paths you would like to create.
            DDD and YYYY will be replaced by the datetime day and year, respectively.

        datetime:
            UTC Datetime string in DOY Format YYYY:DDD:HH:MM:SS

    '''
    # config = CMConfig(paths, datetime)
    for k, path in paths.items():
        try:
            pathlist = path if type(path) is list else [ path ]
            for p in pathlist:
                os.makedirs(p)
                if verbose:
                    bliss.log.info(p)
        except OSError, e:
            if e.errno == errno.EEXIST and os.path.isdir(path):
                pass
            else:
                raise

    return True

if __name__ == '__main__':
    arguments = docopt(__doc__)

    try:
        config = arguments.pop('--config')

        days = int(arguments.pop('--days'))

        length = int(arguments.pop('--length'))

        verbose = arguments.pop('--verbose')

        pathvars = { }

        # read in the config
        if config:
            with open(config, 'rb') as f:
                pathvars = yaml.load(f)

        start = days
        end = days + length

        for d in range(start, end):
            utc = bliss.dmc.getUTCDatetimeDOY(d)

            doy = utc.split(':')
            bliss.log.info('Creating GDS directories for %s:%s' % (doy[0], doy[1]))

            pathvars['year'] = doy[0]
            pathvars['doy'] = doy[1]

            # Add the updated path variables for the date
            bliss.config.addPathVariables(pathvars)

            # Create the directory
            createDirStruct(bliss.config._datapaths, verbose)

    except KeyboardInterrupt:
        bliss.log.info('Received Ctrl-C.  Stopping BLISS Create Directories.')

    except Exception as e:
        print e
        bliss.log.error('BLISS Create Directories error: %s' % str(e))

