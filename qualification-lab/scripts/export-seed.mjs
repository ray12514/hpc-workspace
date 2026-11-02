import {writeFileSync} from 'node:fs';
import {seed} from '../frontend/model.ts';
writeFileSync(new URL('../seed.json',import.meta.url),JSON.stringify(seed,null,2)+'\n');
