from api_pb2 import Cnf
import grpc
from concurrent import futures
import frontier
from grpcbigbuffer.client import parse_from_buffer, serialize_to_buffer
import api_pb2_grpc

class Solver(api_pb2_grpc.Solver):
    def Solve(self, request_iterator, context):
        for b in serialize_to_buffer(
            message_iterator=frontier.ok(
                cnf = next(parse_from_buffer(
                    request_iterator = request_iterator,
                    indices = Cnf,
                    partitions_message_mode=True
                ))
            )
        ): yield b

# create a gRPC server
server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))

api_pb2_grpc.add_SolverServicer_to_server(
    Solver(), server=server
)

print('Starting server. Listening on port 8080.')
server.add_insecure_port('[::]:8080')
server.start()
server.wait_for_termination()
