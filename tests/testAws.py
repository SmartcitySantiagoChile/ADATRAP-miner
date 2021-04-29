from unittest import TestCase, mock

from botocore.exceptions import ClientError

import aws


class AwsTest(TestCase):

    @mock.patch('aws.boto3.Session')
    def setUp(self, boto3_session):
        boto3_session.return_value = mock.MagicMock(resource=mock.MagicMock())
        self.aws_session = aws.AWSSession()

    def test_retrieve_obj_list(self):
        date = mock.MagicMock(size=1000, key='key', last_modified='today')
        dates = mock.Mock(return_value=[date])
        bucket = mock.MagicMock(objects=mock.MagicMock(all=dates))
        bucket.Bucket.return_value = bucket
        self.aws_session.session.resource = mock.MagicMock(return_value=bucket)
        self.assertEqual([{
            'name': 'key',
            'size': 0.00095367431640625,
            'last_modified': 'today',
            'url': 'https://s3.amazonaws.com/bucket_name/key'
        }], self.aws_session.retrieve_obj_list('bucket_name'))

    def test_check_bucket_exists_true(self):
        bucket = mock.MagicMock(
            meta=mock.MagicMock(client=mock.MagicMock(head_bucket=mock.MagicMock(return_value=True))))
        self.aws_session.session.resource = mock.MagicMock(return_value=bucket)
        self.assertTrue(self.aws_session.check_bucket_exists('bucket_name'))

    def test_check_bucket_exists_404_error(self):
        error = mock.MagicMock()
        error_response = {'Error': {'Code': '404'}}
        error.side_effect = ClientError(error_response=error_response, operation_name='mock error')
        bucket = mock.MagicMock(
            meta=mock.MagicMock(client=mock.MagicMock(head_bucket=error)))
        self.aws_session.session.resource = mock.MagicMock(return_value=bucket)
        self.assertFalse(self.aws_session.check_bucket_exists('bucket_name'))

    def test_check_bucket_exists_403_error(self):
        error = mock.MagicMock()
        error_response = {'Error': {'Code': '403'}}
        error.side_effect = ClientError(error_response=error_response, operation_name='mock error')
        bucket = mock.MagicMock(
            meta=mock.MagicMock(client=mock.MagicMock(head_bucket=error)))
        self.aws_session.session.resource = mock.MagicMock(return_value=bucket)

        with self.assertRaises(ValueError):
            self.aws_session.check_bucket_exists('bucket_name')

    def test_check_file_exists(self):
        load = mock.MagicMock()
        load.load.return_value = '2020-05-08.transaction.gz'
        bucket = mock.MagicMock()
        bucket.Object.return_value = load
        self.aws_session.session.resource = mock.MagicMock(return_value=bucket)
        self.assertTrue(self.aws_session.check_file_exists('2020-05-08.transaction.gz', 'key'))

    def test_check_file_exists_404_error(self):
        error = mock.MagicMock()
        error_response = {'Error': {'Code': '404'}}
        error.load.side_effect = ClientError(error_response=error_response, operation_name='mock error')
        bucket = mock.MagicMock()
        bucket.Object.return_value = error
        self.aws_session.session.resource = mock.MagicMock(return_value=bucket)
        self.assertFalse(self.aws_session.check_file_exists('2020-05-08.transaction.gz', 'key'))

    def test_check_file_exists_403_error(self):
        error = mock.MagicMock()
        error_response = {'Error': {'Code': '403'}}
        error.load.side_effect = ClientError(error_response=error_response, operation_name='mock error')
        bucket = mock.MagicMock()
        bucket.Object.return_value = error
        self.aws_session.session.resource = mock.MagicMock(return_value=bucket)
        with self.assertRaises(ValueError):
            self.aws_session.check_file_exists('2020-05-08.transaction.gz', 'key')

    def test__build_url(self):
        url = 'https://s3.amazonaws.com/bucket_name/key'
        self.assertEqual(url, self.aws_session._build_url('key', 'bucket_name'))

    def test_download_object_from_bucket(self):
        bucket = mock.MagicMock(download_file=mock.MagicMock())
        bucket.Bucket.return_value = bucket
        self.aws_session.session.resource = mock.MagicMock(return_value=bucket)
        self.aws_session.download_object_from_bucket('key', 'name', 'path')

    def test__get_available_day_for_op_bucket(self):
        available_days = ['2019-03-01.po.zip', '2019-04-01.po.zip', '2019-07-01.po.zip', '2019-10-12.po.zip', '2020-03-02.po.zip', '2020-06-27.po.zip']
        lower_bound_date = '2019-01-01'
        self.assertIsNone(self.aws_session._get_available_day_for_op_bucket(available_days, lower_bound_date))

        limit_lower_bound_date = '2019-03-01'
        limit_lower_bound_op_date = '2019-03-01.po.zip'
        self.assertEqual(limit_lower_bound_op_date,
                         self.aws_session._get_available_day_for_op_bucket(available_days, limit_lower_bound_date))
        mid_bound_date = '2019-09-03'
        mid_bound_date_op_date = '2019-07-01.po.zip'
        self.assertEqual(mid_bound_date_op_date,
                         self.aws_session._get_available_day_for_op_bucket(available_days, mid_bound_date))

        limit_upper_bound_date = '2020-06-27'
        limit_upper_bound_op_date = '2020-06-27.po.zip'
        self.assertEqual(limit_upper_bound_op_date,
                         self.aws_session._get_available_day_for_op_bucket(available_days, limit_upper_bound_date))
        upper_bound_date = '2020-08-27'
        upper_bound_op_date = '2020-06-27.po.zip'
        self.assertEqual(upper_bound_op_date,
                         self.aws_session._get_available_day_for_op_bucket(available_days, upper_bound_date))
