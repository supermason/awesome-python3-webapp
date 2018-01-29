'''
JSON API definition.
'''


class ApiError(Exception):
    '''
    the base ApiError which contains error(required), data(optional) and message(optional)
    '''

    def __init__(self, error, data='', message=''):
        super(ApiError, self).__init__(message)
        self.error = error
        self.data = data
        self.message = message


class ApiValueError(ApiError):
    '''
    Indicate the input value has error or invalid. The data specifies the error field of input form.
    '''

    def __init__(self, field, message=''):
        super(ApiValueError, self).__init__('value:invalid', field, message)


class ApiResourceNotFoundError(ApiError):
    '''
    Indicate the resource was not found. The data specifies the resource name.
    '''

    def __init__(self, field, message=''):
        super(ApiResourceNotFoundError, self).__init__('value:notfound', field, message)


class ApiPermissionError(ApiError):
    '''
    Indicate the api has no permission.
    '''

    def __init__(self, message=''):
        super(ApiPermissionError, self).__init__('permission:forbidden', 'permission', message)