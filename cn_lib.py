import logging

from pycomm3 import CIPDriver, RequestError, ResponseError
import cip_request

log = logging.getLogger(__name__)


def scan_cn(cip_path, format='', exclude_bp_sn='', p=print, current_cn_node_update=None, max_node_num=99):
    if current_cn_node_update:  # ---------------------------------------------logging function
        cn_node_updt = current_cn_node_update
    else:  # ---------------------------------------------------------------NO logging function
        def cn_node_updt(*args, **kwargs):
            pass

    cn_modules_paths = {}
    cn_modules_identity = {}
    found_controlnet_nodes = []
    p(f'Scanning ControlNet {cip_path}...')

    base = cip_path.rstrip('/')
    driver = CIPDriver(f'{base}/0')
    driver.open()
    try:
        for cnet_node_num in range(max_node_num + 1):  # 100 for production
            target = f'{base}/{cnet_node_num}'
            route = target.split('/', 1)[1]
            request = {
                **cip_request.who,
                'route_path': route,
                'name': f'Who [{cnet_node_num:02}]',
            }
            cn_node_updt(f'{cnet_node_num:02}')

            try:
                cn_module = driver.generic_message(**request)
            except (ResponseError, RequestError) as e:
                log.debug(f'Who [{cnet_node_num:02}]: {e}')
                continue

            if cn_module.error:
                if 'Insufficient resource' in str(cn_module.error):
                    log.error(f'Who [{cnet_node_num:02}]: {cn_module.error}')
                continue

            p(f'{format} found node [{cnet_node_num:02}]')
            m = cip_request.MyModuleIdentityObject.decode(cn_module.value)
            found_controlnet_nodes.append(cnet_node_num)
            cn_modules_paths[m['serial']] = target
            cn_modules_identity[cnet_node_num] = m
    finally:
        try:
            driver.close()
        except Exception:
            pass

    cn_node_updt('--')
    return found_controlnet_nodes, cn_modules_paths, cn_modules_identity
