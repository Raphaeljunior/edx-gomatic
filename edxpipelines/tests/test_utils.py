import mock
import unittest

from ddt import ddt, data, unpack
import edxpipelines.utils as util
from edxpipelines import constants


@ddt
class TestDictMerge(unittest.TestCase):

    @data(({'key1': "value1", "key2": "value2"},  # expected value
           {'key1': "value1"},
           {'key2': "value2"}),

          ({'key1': "value1", "key2": "value2", "key3": "value3", "key4": "value4"},  # expected value
           {'key1': "value1"},
           {'key2': "value2"},
           {'key3': "value3"},
           {'key4': "value4"}),

          ({"key1": {"nested_key1": "nested_value2", "nested_key2": "nested_value2"}},  # expected value
           {"key1": {"nested_key1": "nested_value2"}},
           {"key1": {"nested_key2": "nested_value2"}}),

          ({"key1": {"nested_key1": {"nested_key2": "nested_value2", "nested_key3": "nested_value3"}}},  # expected value
           {"key1": {"nested_key1": {"nested_key2": "nested_value2"}}},
           {"key1": {"nested_key1": {"nested_key3": "nested_value3"}}})
          )
    @unpack
    def test_merge(self, expected, *args):
        self.assertEqual(util.dict_merge(*args), expected)

    @data(({'key1': "value1"},
           {'key1': "value2"}),

          ({'key1': {'key11': "value11"}},
           {'key1': {'key11': "value22"}}),

          ({'key1': ['key11', "value11"]},
           {'key1': {'key11': "value22"}}),

          ({'key1': ['item1', "item2"]},
           {'key1': ['item3', "item4"]})
          )
    @unpack
    def test_merge_collision(self, *args):
        self.assertRaises(util.MergeConflict, util.dict_merge, *args)

    @data(("edxpipelines/tests/files/variables1.yml",
           {'key1': 'value1',
            'key2': 'value2',
            'key3': 'value3'})
          )
    @unpack
    def test_load_yaml_from_file(self, file_path, expected):
        variables = util.load_yaml_from_file(file_path)
        for key, val in expected.iteritems():
            self.assertEqual(variables[key], val)

    @data(
        (
            {
                'key1': 'value1',
                'key10': 'value1',
                'key11': 'value2',
                'key12': 'value3',
                'key2': 'value2',
                'key3': 'value3'
            },  # expected Value
            [
                "edxpipelines/tests/files/variables1.yml",
                "edxpipelines/tests/files/variables2.yml"
            ],
            {'key1': "value1"},
            {'key2': "value2"}
        ),

        (
            {
                'key1': 'value1',
                'key10': 'value1',
                'key11': 'value2',
                'key12': 'value3',
                'key2': 'value2',
                'key3': 'value3',
                'key4': {
                    'nested_key1':
                        {
                            'nested_key2': 'nested_value2',
                            'nested_key3': 'nested_value3',
                            'nested_key4': 'nested_value4',
                            'nested_key5': 'nested_value5'
                        }
                }
            },  # expected Value
            [
                "edxpipelines/tests/files/nested_variables1.yml",
                "edxpipelines/tests/files/variables2.yml"
            ],
            {"key4": {"nested_key1": {"nested_key2": "nested_value2"}}},
            {"key4": {"nested_key1": {"nested_key3": "nested_value3"}}}
        )
    )
    @unpack
    def test_merge_files_and_dicts(self, expected, file_paths, *dicts):
        merged = util.merge_files_and_dicts(file_paths, list(dicts))
        print merged
        self.assertEqual(merged, expected)


@ddt
class TestPipelineHelpers(unittest.TestCase):
    @data(
        ('bmd', 'bmd'),
        ('bdm', 'bmd'),
        ('mbd', 'bmd'),
        ('mdb', 'bmd'),
        ('dmb', 'bmd'),
        ('dbm', 'bmd'),
        ('md', 'md'),
        ('dm', 'md'),
        ('b', 'b'),
    )
    @unpack
    def test_sort_bmd(self, permutation, expected):
        self.assertEqual(util.sort_bmd(permutation), expected)

    @data(
        'bmdc',
        'abcdefg',
        '12356'
    )
    def test_sort_failure(self, permutation):
        """
        Sort should fail if we pass in letters that are not part of the bmd alphabet
        """
        self.assertRaises(Exception, util.sort_bmd, permutation)

    @data(
        'b',
        'bmd',
        'md'
    )
    def test_validate_pipeline_permutations(self, permutation):
        self.assertTrue(util.validate_pipeline_permutations(permutation))

    @data(
        'abc',
        'dmb',
        'dm',
        'bmmd',
        'bbmdd'

    )
    def test_invalid_pipeline_permutations(self, permutation):
        self.assertRaises(Exception, util.validate_pipeline_permutations, permutation)

    @data(
        ('blah', 'bmd', ('blah_B-M-D', 'blah_B-M-D')),
        ('blah', 'md', ('blah_M-D', 'blah_B')),
        ('blah', 'b', ('blah_B', 'blah_B')),
    )
    @unpack
    def test_determine_pipeline_names(self, config, bmd_steps, expected_tuple):
        self.assertEqual(util.determine_pipeline_names(config, bmd_steps), expected_tuple)

    @data(
        ('blah', 'dmb'),
    )
    @unpack
    def test_invalid_input_determine_pipeline_names(self, config, bmd_steps):
        self.assertRaises(KeyError, util.determine_pipeline_names, config, bmd_steps)
