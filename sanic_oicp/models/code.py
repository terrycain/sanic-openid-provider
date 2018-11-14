import datetime
import logging
import uuid
from typing import Dict, Tuple, Any, Union, Optional, TYPE_CHECKING

from sanic_oicp.utils import masked

import aioboto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.config import Config

if TYPE_CHECKING:
    from sanic_oicp.models.clients import Client


logger = logging.getLogger('oicp')


class CodeStore(object):
    def __init__(self, provider):
        self._provider = provider

    def set_provider(self, provider):
        self._provider = provider

    async def setup(self):
        pass

    async def create_code(self,
                          client: 'Client',
                          user: Dict[str, Any],
                          scopes: Tuple[str, ...],
                          code_expire: int,
                          nonce: str=None,
                          code_challenge: str=None,
                          code_challenge_method: str=None,
                          specific_claims: Dict[str, Any]=None):
        if specific_claims is None:
            specific_claims = {}

        code = {
            'used': False,
            'user': user['username'],
            'client': client.id,
            'code': uuid.uuid4().hex,
            'code_challenge': code_challenge,
            'code_challenge_method': code_challenge_method,
            'expires_at': int(datetime.datetime.now().timestamp() + code_expire),
            'scope': scopes,
            'nonce': nonce,
            # 'is_authentication': is_authentication,
            'specific_claims': specific_claims
        }

        await self._save_code(code)

        return code

    async def _save_code(self, code: Dict[str, Any]):
        raise NotImplementedError()

    async def get_by_id(self, id_: str) -> Union[Dict[str, Any], None]:
        raise NotImplementedError()

    async def mark_used_by_id(self, id_: str):
        raise NotImplementedError()


class InMemoryCodeStore(CodeStore):
    def __init__(self, *args, **kwargs):
        super(InMemoryCodeStore, self).__init__(*args, **kwargs)

        self._store: Dict[str, Any] = {}

    async def _save_code(self, code: Dict[str, Any]):
        self._store[code['code']] = code
        logger.info('Saved code {0}'.format(masked(code['code'])))

    async def get_by_id(self, id_: str) -> Union[Dict[str, Any], None]:
        try:
            code = self._store[id_]

            now = int(datetime.datetime.now().timestamp())
            if now > code['expires_at']:
                del self._store[id_]
                logger.info('Code expired, removing')
                return None

            return code
        except KeyError:
            pass

        return None

    async def mark_used_by_id(self, id_: str):
        try:
            code = self._store[id_]

            code['used'] = True
            logger.info('Marked code {0} as used'.format(masked(code['code'])))
        except KeyError:
            pass


class DynamoDBCodeStore(CodeStore):
    def __init__(self, *args, table_name: str='oidc-codes', region: str='eu-west-1', boto_config: Optional[Config]=None, **kwargs):
        super(DynamoDBCodeStore, self).__init__(*args, **kwargs)

        self._table_name = table_name
        self._region = region
        self._boto_config = boto_config
        self._dynamodb_resource = None
        self._table = None

    async def setup(self):
        self._dynamodb_resource = aioboto3.resource('dynamodb', region_name=self._region, config=self._boto_config)
        self._table = self._dynamodb_resource.Table(self._table_name)

    async def _save_code(self, code: Dict[str, Any]):
        try:
            await self._table.put_item(Item=code)
            logger.info('Saved code {0}'.format(masked(code['code'])))
        except Exception as err:
            logger.exception('Failed to save code {0}'.format(masked(code['code'])), exc_info=err)

    async def get_by_id(self, id_: str) -> Union[Dict[str, Any], None]:
        try:
            resp = await self._table.get_item(Key={'code': id_})
            if 'Item' in resp:
                return resp['Item']
        except Exception as err:
            logger.exception('Failed to get code {0}'.format(masked(id_)), exc_info=err)
        return None

    async def mark_used_by_id(self, id_: str):
        try:
            await self._table.update_item(
                Key={'code': id_},
                UpdateExpression='SET used = :u',
                ExpressionAttributeValues={
                    ':u': True
                }
            )
            logger.info('Marked code {0} as used'.format(masked(id_)))
        except KeyError:
            pass


oigh';bjsretiojgsrethg'
#TODO check code expires_at