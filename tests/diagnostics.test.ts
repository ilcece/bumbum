import {test} from 'node:test';
import assert from 'node:assert/strict';
import {safeErrorDetails} from '../src/diagnostics.js';
test('safe diagnostics preserve type and known code locations without exception contents',()=>{
 const e={name:'TypeError',code:'ER_TABLEACCESS_DENIED_ERROR',message:'password=PRIVATE_PASSWORD phone=13800000001',stack:'TypeError: PRIVATE_PASSWORD\nSQL SELECT password_hash\n    at login (/app/dist/app.js:205:14)\n    at pool (/app/node_modules/mysql2/pool.js:10:2)\n    at bad (/private/PRIVATE_PASSWORD:1:1)'};
 const details=safeErrorDetails(e);
 assert.deepEqual(details,{errorType:'TypeError',errorCode:'ER_TABLEACCESS_DENIED_ERROR',sites:['app:205:14']});
 assert.doesNotMatch(JSON.stringify(details),/PRIVATE_PASSWORD|13800000001|password_hash|SELECT/);
});
test('malformed or sensitive diagnostic fields are discarded',()=>{
 assert.deepEqual(safeErrorDetails({name:'PRIVATE_PASSWORD',code:'password=PRIVATE_PASSWORD',stack:'message /app/dist/app.js:1:1'}),{errorType:'Error',sites:[]});
 assert.deepEqual(safeErrorDetails(null),{errorType:'Error',sites:[]});
});
