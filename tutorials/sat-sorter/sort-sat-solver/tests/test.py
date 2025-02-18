import os
import shutil
import sys
from time import sleep, time
from typing import Final, Optional

import grpc
import json
import threading
from grpcbigbuffer.client import Dir, client_grpc
from grpcbigbuffer.utils import modify_env

from protos import api_pb2, api_pb2_grpc, solvers_dataset_pb2
from node_controller.gateway.protos.gateway_pb2_grpcbf import StartService_input_indices
from node_controller.gateway.protos import gateway_pb2, celaut_pb2, gateway_pb2_grpc


GATEWAY="192.168.1.20:53047"
SORTER_ENDPOINT=None
CLIENT_DEV="dev-5159b09f-d431-4455-90ca-08f462e0ec02"
LOCAL_SOLVER = True
LOCAL_RANDOM = True

RANDOM="54500441c6e791d9f6ef74102f962f1de763c9284f17a8ffde3ada9026d55089"
FRONTIER="2985edc25e91e4039214ebe632ba8a3b1c4f77fcc68faf3441339cd011a98947"
SORTER="906e9c99614942b17aa1409332173a6b22ed1c86fccddc880247016b8cb203b5"

METADATA_REGISTRY="/nodo/storage/__metadata__"
REGISTRY="/nodo/storage/__registry__"
modify_env(block_dir="/nodo/storage/__block__/")

SHA3_256_ID: Final[bytes] = bytes.fromhex("a7ffc6f8bf1ed76651c14756a061d662f580ff4de43b49fa82d80a4b80f8434a")
SHA3_256 = SHA3_256_ID.hex()

LIST_OF_SOLVERS = [FRONTIER] if FRONTIER else []
TEST_DATA_STORAGE = f'test_storage'
os.makedirs(TEST_DATA_STORAGE, exist_ok=True)
SESSION_SERVICES_JSON: Final[str] = f'{TEST_DATA_STORAGE}/script_data.json'

def to_gas_amount(gas_amount: int) -> gateway_pb2.GasAmount:
    return gateway_pb2.GasAmount(n=str(gas_amount))

def generator(_hash: str, mem_limit: int = 50 * pow(10, 6), initial_gas_amount: Optional[int] = None):
    try:
        yield gateway_pb2.Client(client_id=CLIENT_DEV)

        yield gateway_pb2.Configuration(
            config=celaut_pb2.Configuration(),
            resources=gateway_pb2.CombinationResources(
                clause={
                    1: gateway_pb2.CombinationResources.Clause(
                        cost_weight=1,
                        min_sysreq=celaut_pb2.Sysresources(
                                mem_limit=mem_limit
                            )
                    )
                }
            ),
            initial_gas_amount=to_gas_amount(initial_gas_amount) if initial_gas_amount else None
        )

        yield celaut_pb2.Any.Metadata.HashTag.Hash(
                type=bytes.fromhex(SHA3_256),
                value=bytes.fromhex(_hash)
            )

        yield Dir(
            dir=os.path.join(METADATA_REGISTRY, _hash),
            _type=celaut_pb2.Any.Metadata
        )

        yield Dir(
            dir=os.path.join(REGISTRY, _hash),
            _type=celaut_pb2.Service
        )

    except Exception as e:
        print(f"Exception on tests: {e} with the hash  {_hash}")

def test_sorter_service(sorter_endpoint: Optional[str] = sys.argv[3] if len(sys.argv) == 4 else None):
    def is_good(cnf, interpretation):
        def good_clause(clause, interpretation):
            for var in clause.literal:
                for i in interpretation.variable:
                    if var == i:
                        return True
            return False

        for clause in cnf.clause:
            if not good_clause(clause, interpretation):
                return False
        return True

    # Start the script.

    if input('Clean json data? (y/n)') == 'y':
        print('\nClearing data ...')
        with open(SESSION_SERVICES_JSON, 'w') as file:
            json.dump("", file)

    g_stub = gateway_pb2_grpc.GatewayStub(
        grpc.insecure_channel(GATEWAY)
    )

    sleep(5)

    print(json.load(open(SESSION_SERVICES_JSON, 'r')))
    if type(json.load(open(SESSION_SERVICES_JSON, 'r'))) != dict:

        print('Get new services....')

        if not sorter_endpoint:
            if not os.path.exists(os.path.join(REGISTRY, SORTER)):
                raise Exception(f"{SORTER} service not exists.")
            print(f"Get the sorter {SORTER}")
            try:
                # Get a classifier.
                classifier = next(client_grpc(
                    method=g_stub.StartService,
                    input=generator(
                        _hash=SORTER,
                        mem_limit= 630 * pow(10, 6),
                        initial_gas_amount=pow(10, 64)
                    ),
                    indices_parser=gateway_pb2.Instance,
                    partitions_message_mode_parser=True,
                    indices_serializer=StartService_input_indices
                ))
            except Exception as e:
                print(f"Exception getting the sorter service -> {e}")
                raise e
            print(classifier)
            uri = classifier.instance.uri_slot[0].uri[0]
            c_uri = uri.ip + ':' + str(uri.port)
        else:
            c_uri = sorter_endpoint
        c_stub = api_pb2_grpc.SolverStub(
            grpc.insecure_channel(c_uri)
        )
        print('We have classifier ', c_stub)
        
        sleep(10)

        if LOCAL_RANDOM:
            print("Get random cnf")
            # Get random cnf
            random_cnf_service = next(client_grpc(
                method=g_stub.StartService,
                input=generator(_hash=RANDOM),
                indices_parser=gateway_pb2.Instance,
                partitions_message_mode_parser=True,
                indices_serializer=StartService_input_indices
            ))
            print(random_cnf_service)
            uri = random_cnf_service.instance.uri_slot[0].uri[0]
            r_uri = uri.ip + ':' + str(uri.port)
            r_stub = api_pb2_grpc.RandomStub(
                grpc.insecure_channel(r_uri)
            )
            print('Received random. ', r_stub)
        
            sleep(10)

        if FRONTIER != '' and LOCAL_SOLVER:
            print("Get local frontier")
            # Get the frontier for test it.
            frontier_service = next(client_grpc(
                method=g_stub.StartService,
                input=generator(_hash=FRONTIER),
                indices_parser=gateway_pb2.Instance,
                partitions_message_mode_parser=True,
                indices_serializer=StartService_input_indices,
            ))
            uri = frontier_service.instance.uri_slot[0].uri[0]
            frontier_uri = uri.ip + ':' + str(uri.port)
            frontier_stub = api_pb2_grpc.SolverStub(
                grpc.insecure_channel(frontier_uri)
            )

            print('Received frontier ', frontier_stub)

        # save stubs on json.
        with open(SESSION_SERVICES_JSON, 'w') as file:
            json.dump({
                'sorter': c_uri,
                'random': r_uri if LOCAL_RANDOM else "",
                'frontier': frontier_uri if LOCAL_SOLVER else "",
            }, file)

    else:
        print('Getting from json file.')
        with open(SESSION_SERVICES_JSON, 'r') as file:
            data = json.load(file)
            print(data)
            c_stub = api_pb2_grpc.SolverStub(
                grpc.insecure_channel(data['sorter'])
            )
            r_stub = api_pb2_grpc.RandomStub(
                grpc.insecure_channel(data['random'])
            )
            try:
                if LOCAL_SOLVER:
                    frontier_stub = api_pb2_grpc.SolverStub(
                        grpc.insecure_channel(data['frontier'])
                    )
            except:
                pass

    sleep(10)  # Espera a que el servidor se levante.

    print('Uploading solvers al clasificador.')
    for s in LIST_OF_SOLVERS:
        print('     ', s)
        while input("\n Upload the solver? (y/n)") == 'y':
            try:
                next(client_grpc(
                    method=c_stub.UploadSolver,
                    indices_serializer={
                        1: celaut_pb2.Any.Metadata,
                        2: celaut_pb2.Service,
                    },
                    input=(
                        Dir(dir=os.path.join(METADATA_REGISTRY, s), _type=celaut_pb2.Any.Metadata),
                        Dir(dir=os.path.join(REGISTRY, s), _type=celaut_pb2.Service)
                    )
                ))
                break
            except Exception as e:
                print('Error connecting to the classifier ', e)
                sleep(1)

    try:
        dataset = solvers_dataset_pb2.DataSet()
        dataset.ParseFromString(open('dataset.bin', 'rb').read())
        next(client_grpc(
            method=c_stub.AddDataSet,
            input=dataset
        ))
        print('Dataset added.')
    except Exception as e:
        print("Don't have dataset")
        pass

    if input("\nGo to train? (y/n)")=='y':
        print('Starting training ...')
        next(client_grpc(
            method=c_stub.StartTrain
        ))

        print('Wait to train the model ...')
        for i in range(200):

            sleep(5)

            if LOCAL_RANDOM:
                try:
                    cnf = next(client_grpc(
                        method=r_stub.RandomCnf,
                        partitions_message_mode_parser=True,
                        indices_parser=api_pb2.Cnf
                    ))
                except Exception as e:
                    print(f"Error getting a random cnf. Exception {e}")
                    exit()
                    
                # Comprueba si sabe generar una interpretacion (sin tener ni idea de que tal
                # ha hecho la seleccion del solver.)
                print('\n ---- ', i)

                print(f' SOLVING CNF ... {cnf}')
                t = time()
                try:
                    try:
                        interpretation = next(client_grpc(
                            method=c_stub.Solve,
                            indices_parser=api_pb2.Interpretation,
                            partitions_message_mode_parser=True,
                            input=cnf,
                            indices_serializer=api_pb2.Cnf,
                            timeout=200
                        ))
                        
                        print(str(time() - t) + ' OKAY THE INTERPRETATION WAS ', interpretation, '.',
                                is_good(cnf=cnf, interpretation=interpretation))
                    except:
                        print("Any interpretation from the sat-sorter service ....")
                        interpretation = None

                    print(' SOLVING CNF ON DIRECT SOLVER ...')
                    if LOCAL_SOLVER:
                        t = time()
                        try:
                            interpretation = next(client_grpc(
                                method=frontier_stub.Solve,
                                input=cnf,
                                indices_serializer=api_pb2.Cnf,
                                partitions_message_mode_parser=True,
                                indices_parser=api_pb2.Interpretation
                            ))
                        except(grpc.RpcError):
                            # Get the frontier for test it.
                            uri = next(client_grpc(
                                method=g_stub.StartService,
                                input=generator(_hash=FRONTIER),
                                indices_parser=gateway_pb2.Instance,
                                partitions_message_mode_parser=True,
                                indices_serializer=StartService_input_indices
                            )).instance.uri_slot[0].uri[0]
                            frontier_uri = uri.ip + ':' + str(uri.port)
                            frontier_stub = api_pb2_grpc.SolverStub(
                                grpc.insecure_channel(frontier_uri)
                            )
                            interpretation = next(client_grpc(
                                method=frontier_stub.Solve,
                                input=cnf,
                                indices_serializer=api_pb2.Cnf,
                                partitions_message_mode_parser=True,
                                indices_parser=api_pb2.Interpretation
                            ))
                        print(str(time() - t) + ' OKAY THE FRONTIER SAID ', interpretation, '.',
                            is_good(interpretation=interpretation, cnf=cnf))

                except Exception as e:
                    print('Solving cnf error -> ', str(e), ' may the tensor is not ready')

            print('Received the data_set.')

            dataset_obj = next(client_grpc(
                method=c_stub.GetDataSet,
                indices_parser=solvers_dataset_pb2.DataSet,
                partitions_message_mode_parser=False
            ))
            shutil.copyfile(
                dataset_obj.dir,
                'dataset.bin'
            )

            sleep(5)

        sleep(100)

    print('Ends the training')
    next(client_grpc(
        method=c_stub.StopTrain
    ))

    # "Check if it knows how to generate an interpretation (without having any idea how the solver selection was done)."
    def final_test(c_stub, r_stub, i, j):
        cnf = next(
            client_grpc(
                
                method=r_stub.RandomCnf, 
                indices_parser=api_pb2.Cnf, 
                partitions_message_mode_parser=True
            ))
        t = time()
        interpretation = next(client_grpc(
            
            method=c_stub.Solve,
            input=cnf,
            indices_serializer=api_pb2.Cnf,
            partitions_message_mode_parser=True,
            indices_parser=api_pb2.Interpretation
        ))
        print(interpretation, str(time() - t) + 'THE FINAL INTERPRETATION IN THREAD ' + str(threading.get_ident()),
              ' last time ', i, j)

    if LOCAL_RANDOM:
        for i in range(3):
            sleep(10)
            threads = []
            for j in range(10):
                t = threading.Thread(target=final_test, args=(c_stub, r_stub, i, j,))
                threads.append(t)
                t.start()
            for t in threads:
                t.join()

    print('Received the data_set.')
    dataset_it = client_grpc(
        method=c_stub.GetDataSet,
        indices_parser=solvers_dataset_pb2.DataSet,
        partitions_message_mode_parser=False
    )
    dataset_obj = next(dataset_it)
    print(dataset_obj, type(dataset_obj))
    if type(dataset_obj) != str:
        dataset_obj = next(dataset_it)
        print(dataset_obj, type(dataset_obj))
    shutil.copyfile(
        dataset_obj,
        'dataset.bin'
    )

    print('waiting for kill solvers ...')
    for i in range(10):
        for j in range(10):
            sleep(10)
            print(i, j)

    # Stop the classifier.
    print('Stop the classifier.')
    try:
        next(client_grpc(
            method=g_stub.StopService,
            input=gateway_pb2.TokenMessage(token=classifier.token)
        ))
    except Exception as e:
        print('e -> ', e)

    # Stop Random cnf service.
    print('Stop the random.')
    try:
        next(client_grpc(
            method=g_stub.StopService,
            input=gateway_pb2.TokenMessage(token=random_cnf_service.token)
        ))
    except Exception as e:
        print('e -> ', e)

    # Stop Frontier cnf service.
    print('Stop the frontier.')
    try:
        next(client_grpc(
            method=g_stub.StopService,
            input=gateway_pb2.TokenMessage(token=frontier_service.token)
        ))
    except Exception as e:
        print('e -> ', e)

    print('All good?')

    with open(SESSION_SERVICES_JSON, 'w') as file:
        print('Clearing data ...')
        json.dump("", file)

if __name__ == "__main__":
    test_sorter_service(sorter_endpoint=SORTER_ENDPOINT)
