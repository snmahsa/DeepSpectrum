import argparse
from os import makedirs
from os.path import dirname, basename, splitext, abspath, join

from .ds_help import DESCRIPTION_RESULTS
from ..learn.metrics import KEY_TO_METRIC, UAR
from ..learn.results import ResultSet, CVResultSet, EvalPartitionResultSet, compare

__SHOW = 'show'
__EXPORT = 'export'
__IMPORT = 'import'
__COMPARE = 'compare'
__FUSE = 'fuse'


def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    subparsers = parser.add_subparsers(
        help=DESCRIPTION_RESULTS)
    __show_subparser(subparsers)
    __export_subparser(subparsers)
    __import_subparser(subparsers)
    __compare_subparser(subparsers)

    return parser.parse_args()


def __show_subparser(subparsers):
    parser = subparsers.add_parser(
        __SHOW,
        help='Show a json result set generated by ds-scikit on the commandline.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'input',
        help='The json result file to be shown.')
    parser.set_defaults(action=__show)


def __show(args):
    results = ResultSet.load(args.input)
    print(results)


def __export_subparser(subparsers):
    parser = subparsers.add_parser(
        __EXPORT,
        help='Export predictions of a json result set to csv-Files. The predictions are saved as '
             '"predictions_{results}.csv" in the case of a standard evaluation result set. '
             'If the results belong to a CrossValidation experiment, predictions for each fold and also the combined predictions are saved.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'input',
        help='The json result file to export predictions from.')
    parser.add_argument(
        '-od', '--output_dir', default=None,
        help='The directory for the predictions. If omitted, saves predictions to directory of results.')
    parser.set_defaults(action=__export)


def __import_subparser(subparsers):
    parser = subparsers.add_parser(
        __IMPORT,
        help='Import a result set from prediction csv(s). Can create a simple eval partition result set or a cross-validation result set, depending on the number of passed prediction csv files.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'input',
        help='The prediction files to import into a resultset. Creates a crossvalidation resultset if you pass multiple prediction csv files (each belonging to a specific fold).',
        nargs='+')
    parser.add_argument(
        '-o', '--output', default=None,
        help='Name of the resultset file to be created. Defaults to "results.json" in the directory of input.')
    parser.set_defaults(action=__import)


def __import(args):
    print(f'Loading predictions from "{args.input}"')
    if len(args.input) > 1:
        print(f'Importing predictions as {CVResultSet.__name__}')
    else:
        print(f'Importing predictions as {EvalPartitionResultSet.__name__}')

    result_set = ResultSet.from_csv(csvs=args.input)
    if args.output is None:
        args.output = join(dirname(args.input[0]), 'results.json')
    makedirs(dirname(abspath(args.output)), exist_ok=True)
    print(result_set)
    result_set.save(abspath(args.output))
    print(f'Saved result set to "{abspath(args.output)}"')


def __compare_subparser(subparsers):
    parser = subparsers.add_parser(
        __COMPARE,
        help='Compare two result sets. Depending on the type of results (Crossvalidation or simple evaluation) different statistical methods will be employd.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'input',
        help='The results to compare.',
        nargs=2)
    parser.add_argument('-m', '--metric', type=str, choices=KEY_TO_METRIC.keys(),
                        default=UAR.__name__,
                        help='Metric that should be used for comparing the results.')
    parser.set_defaults(action=__compare)


def __compare(args):
    first_result = ResultSet.load(args.input[0], comparison_metric=KEY_TO_METRIC[args.metric])
    second_result = ResultSet.load(args.input[1], comparison_metric=KEY_TO_METRIC[args.metric])
    description, stats = compare(first_result, second_result, KEY_TO_METRIC[args.metric])
    print(description)
    print("\nStatistics:")
    for key, value in stats.items():
        print(f'\n {key}:\n   statistic: {value[0]}\n   pvalue: {value[1]}\n')


def __export(args):
    print(f'Loading results from: "{args.input}"')
    results = ResultSet.load(args.input)
    if args.output_dir is None:
        args.output_dir = dirname(abspath(args.input))
    print(f'Exporting predictions to: "{args.output_dir}"')
    results.export_predictions(dirname(args.input), prefix=splitext(basename(args.input))[0])


def main():
    args = parse_args()
    args.action(args)


if __name__ == '__main__':
    main()