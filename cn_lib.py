from pycomm3 import CIPDriver, ResponseError
import cip_request

def scan_cn(cip_path, format='', exclude_bp_sn='', p=print, current_cn_node_update=None, max_node_num=99):
    if current_cn_node_update:  # ---------------------------------------------logging function
        cn_node_updt = current_cn_node_update
    else:  # ---------------------------------------------------------------NO logging function
        def cn_node_updt(*args, **kwargs):
            pass

    cn_modules_paths = {}
    found_controlnet_nodes = []
    p(f'Scanning ControlNet {cip_path}...')
    for cnet_node_num in range(max_node_num + 1):  # 100 for production
        target = f'{cip_path}/{cnet_node_num}'
        cn_node_updt(f'{cnet_node_num:02}')
        # time.sleep(0.02)

        # print(f' Scan address {cnet_node_num}')
        try:
            driver = CIPDriver(target)
            driver.open()
            cn_module = driver.generic_message(**cip_request.who)
            if cn_module.error:
                # no module. CN address not in use
                # print('.', end='')
                pass
            else:
                p(f'{format} found node [{cnet_node_num:02}]')
                m = cip_request.MyModuleIdentityObject.decode(cn_module.value)
                # p(m)
                found_controlnet_nodes.append(cnet_node_num)
                cn_modules_paths[m['serial']] = target
            driver.close()
        except ResponseError:
            # print('.', end='')
            driver.close()
    cn_node_updt('--')
    # print('-'*20)
    # pprint(cn_modules_paths)
    return found_controlnet_nodes, cn_modules_paths