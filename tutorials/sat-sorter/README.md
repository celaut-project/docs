This tutorial mainly consists of developing the SAT solver classification service. 

**SAT** stands for **Boolean Satisfiability**. It is the problem of determining whether there exists an assignment of truth values (true/false) to variables in a Boolean formula that makes the entire formula evaluate to true.

In this context:

- **CNF (Conjunctive Normal Form):** The Boolean formulas you're dealing with are expressed in CNF, which means they are written as an AND of clauses, where each clause is an OR of literals (a variable or its negation).
  
- **SAT Solver:** A SAT solver is a program that takes a CNF formula as input and determines whether there is a satisfying assignment. If the formula is satisfiable, the solver might also provide an example of such an assignment.

- **SAT-solver classification service:** The service is designed to not only solve CNF problems but also classify them in order to select the most suitable SAT solver. This means the system might analyze the characteristics of a given CNF and, based on training with random CNFs, decide which solver will perform best on that particular problem.

## Classification Service  

The service performs several tasks simultaneously. Like the node, Python 3 has been chosen as the technology for developing its logic. The entry point of the service is the `start.py` file, where the Grpc server is started after accessing the service's initial configuration (the `__config__` file provided by the node), retrieving environment variables, and launching various background processes.  

It uses a service to obtain random CNFs, requesting an instance of this service at the start of each training session and terminating it at the end of the session. In addition to this dependency, it also integrates various solvers, which can be added by the client via the Grpc server. The random CNF retrieval service was not developed during the project but rather adapted—it uses code from Professor Josep Argelich, so its logic will not be detailed in this documentation. This service returns a CNF of any type, whether satisfiable or unsatisfiable.  

It also makes use of a service for obtaining a linear regression model from a dataset. This will be discussed later.  

The Grpc server provides a series of methods for handling client requests, as shown in Figure 7. These methods are:  

- **StartTrain**: Starts a training session if one is not already active.  
- **StopTrain**: Stops the training session if it exists.  
- **UploadSolver**: Receives the specification of a SAT-solving service and adds it to the system.  
- **StreamLogs**: Returns system logs via streaming.  
- **Solve**: Receives a CNF, determines the best solver for it, and solves it accordingly. Finally, it returns the result.  
- **GetTensor**: Retrieves the trained linear regression model.  
- **AddTensor**: Allows adding a model to be combined with the one already in the service. This method is not implemented.  
- **GetDataSet**: Retrieves the dataset obtained from training, used to train the model.  
- **AddDataSet**: Receives a new dataset and merges it with the existing one in the service.  

### Main Components of the Service Logic  

#### Regression Interface  

Located in the `regresion.py` file. During the startup of the main process (`start.py`), the `regresion.Session` object is instantiated following the Singleton pattern. This object is used throughout the service’s lifecycle. It is responsible for instantiating and providing methods for utilizing the linear regression service while ensuring its maintenance, including error control and managing the creation and suspension of instances with the node. If a certain number of errors occur, the instance is destroyed and a new one is requested.  

Additionally, it holds the main dataset and provides methods for adding both training-generated data and data provided by the client, as well as the most recent regression model.  

A secondary thread is executed to periodically run the regression and save the model in the classification service every predefined interval (`TIME_FOR_EACH_REGRESION_LOOP: 900 seconds by default`).  

The formula for merging two datasets is:  

\[
\frac{i*\overline{S_i} + j*\overline{S_j}} {i+1} = \overline{S_{i+j}}
\]  


#### Training System  

Located in the `train.py` file. During the startup process (`start.py`), the `trainer.Session` object is obtained, which follows the Singleton pattern. This object is used throughout the service's lifecycle.  

The `train.Session` object is responsible for:  
- Managing the service for obtaining random CNFs.  
- Executing the training session.  
- Stopping the training session.  
- Adding new data.  

When a training session is started (`StartTrain` method) from the main thread, a new thread is created to execute the `init` method. This method starts a random CNF service and, in each iteration, generates a CNF and tests it with each solver. The process stops only when the `do_stop` variable is signaled from the main thread using the `StopTrain` method.  

##### Solver Scoring System  

The score a solver receives for solving a CNF is inversely proportional to the time it takes to respond. If the solver takes too long to respond (a timeout is applied in the GRPC call, controlled by the environment variable `TRAIN_SOLVERS_TIMEOUT`, with a default of 30 seconds), it receives a negative score of `-1/time_out`.  

If the solver returns an interpretation, it is checked to see if it satisfies the CNF (a polynomial-time operation). If it does, the solver is scored positively as `+1/time`, and it is recorded that the CNF was proven satisfiable. If the interpretation does not satisfy the CNF, the solver is scored negatively as `-1/time`.  

If a solver determines that the CNF is unsatisfiable, the time taken is recorded. After testing all solvers with that CNF, if at least one solver proves its satisfiability, the solvers that declared it unsatisfiable are scored negatively (`-1/time`). Otherwise, they receive a positive score (`+1/time`).  

The score increment for a specific CNF for a given solver is calculated as follows:  

\[
\frac{\sum_{i=1}^{i} S + S_{i+1}}{i+1}=\overline{S_{i+1}} \Longrightarrow \frac{i*\overline{S_i} + S_{i+1}}{i+1}=\overline{S_{i+1}}
\]

##### Data Management During Training  

Every certain number of iterations (`SAVE_TRAIN_DATA`: default is 10 unless specified otherwise in the environment variable), the dataset is added to the main dataset used by the regression interface. The data generated during the iteration is then deleted.  

Failing to reset the data each time it is added to the main dataset would cause an imbalance in the mean of each data point, giving more importance to older data.  

##### Management of the Random CNF Generation Service  

A new instance of the CNF generation service is created at the start of each training session and destroyed when the session ends. Additionally, a new instance must be requested if the current instance accumulates a certain number of errors (`CONNECTION_ERRORS`: default is 5). These errors can arise when requesting a new CNF, either due to a GRPC error or a timeout.  

##### Training Termination Mechanism  

To prevent the `stop` method (used by the `StopTrain` method of the GRPC server in `start.py`) from forcibly terminating a thread during training, the `stop` method signals that the training should stop on the next iteration. It then waits for the training process to exit the loop and finish properly.  

This approach ensures that no instances are left outside the stack, preventing zombie instances.  


#### Solver Manager  

Located in the `_solve.py` file. During the startup process (`start.py`), the `solve.Session` object is obtained, which follows the Singleton pattern. This object is used throughout the service's lifecycle.  

The `solve.Session` object is responsible for:  
- Managing instances of all solvers.  
- Requesting a specific solver to solve a given CNF.  
- Balancing requests among multiple instances of the same solver when necessary.  

A secondary thread runs periodically (`MAINTENANCE_SLEEP_TIME`: default is 100 seconds) to check the status of solver instances. It does this by verifying whether they are still active by solving a basic CNF (`[[1,]]`). If an error is encountered, the instance is destroyed.  

##### Adding and Managing Solvers  

The `solve.Session` object also provides a method for adding new solvers to its registry. These solvers are stored in a dictionary of type `identifier:SolverConfig`.  

The `SolverConfig` object defines a solver service along with its specific configuration.  

##### Solving CNFs  

The `solve.Session` object allows solving CNFs by providing:  
- A CNF formula.  
- The identifier of a solver with a given configuration.  
- An optional timeout for the operation.  
- An optional solver specification along with its configuration (in case the solver is not found by its identifier).  

If the solver is already registered, it processes the CNF and returns the result along with the time taken to solve it. If the solver is not found but a specification is provided, it is added to the registry, and an error is returned.  

##### Request Balancing  

If multiple requests to solve CNFs are made simultaneously, a situation may arise where a specific solver is required at the same time. A solver may be capable of solving multiple CNFs concurrently within the same container, but this approach does not fully utilize the advantages of a distributed system.  

To allow multiple CNFs to be solved simultaneously by the same solver, the classifier creates multiple instances of the solver when necessary. This ensures that the service is distributed across different nodes in the network.  

+--------------------+
|      Session      |
+--------------------+
| - ENVS: ...       |
| - solvers: dict   |
| - gateway stub:   |
|   Grpc Stub       |
+--------------------+
| + cnf            |
| + maintenance    |
| + add solver    |
+--------------------+
        |
        | 0..*
        v
+----------------------------+
|      Solver Config        |
+----------------------------+
| - service espec.:         |
|   ipss.Service            |
| - configuration:          |
|   ipss.Configuration      |
| - instances: list of      |
|   SolverInstances         |
+----------------------------+
| + service extended       |
| + launch instance       |
| + add instance         |
| + get instance        |
+----------------------------+
        |
        | 0..*
        v
+----------------------------+
|     Solver Instance       |
+----------------------------+
| - stub: Grpc Stub        |
| - token: string         |
| - creation date time:   |
|   Time                 |
| - use date time: Time  |
| - pass timeout: int    |
| - failed attempts: int |
+----------------------------+
| + iszombie             |
| + stop                |
| + check if is alive  |
+----------------------------+



As observed in the previous diagram, to manage the instances of each solver,  
a dictionary structure of solvers is adopted (`<solver_config_id>:<SolverConfig object>`),  
where each `SolverConfig` object contains a list of instances (`SolverInstance` objects).  
When an instance of a specific solver is required, it is removed from the list, and when it is no longer needed,  
it is reintroduced into the list.  

Access to the entire dictionary is protected against concurrency using a `threading.Lock` object.  
The identifier of a `SolverConfig` object is obtained using the SHA3-256 hash algorithm of its Protobuf binary.  

Figure 9 illustrates the stack usage of instances for a single solver:

                           +------------------+
                           | Instance         |
                           | Instance         |
                           | Instance         |
                           +------------------+
                               |   ^    |
              1 TAKE Instance  |   |    | 3 APPEND Instance
                               |   |    |
      +---------------+        |   |    |        +----------------+
      |  CNF method   |--------+   +----+--------| MAINTAINER     |
      +---------------+                     |    |    method      |
           |   ^                            |    +----------------+
      2 USE|   |                            |         ^    |
           |   |                            |         |    | 2 VERIFY Instance
           +---+----------------------------+---------+
              3 APPEND Inst.


There are two methods that retrieve and insert instances into the lists:  
resolving a CNF (`Session.cnf`) and the maintenance thread (`Session.maintenance`).  

The method for resolving a CNF uses the list as a standard stack, meaning:  
it takes the element at the highest index in the list and places the element back at the highest index.  

The maintenance method, however, treats the list as a reverse stack:  
it takes the element at the first position of the list and places the element back in the first position.  

This configuration is adopted because instances have counters tracking the last time they were used.  
These counters are only updated when resolving CNFs (via `Session.cnf`).  
When the instance maintainer retrieves an instance, it checks if it has exceeded the idle time limit.  
If so, it is not reinserted into the list; otherwise, it is placed at the first position.  
This ensures that instances at higher positions have been used more recently.  

When an instance is taken, it must be ensured that after use, it is either added back to its corresponding list  
or a request is made to the node to stop it.  

Failing to ensure this leads to a critical bug, as the instance would remain in a zombie state  
until the classifier is removed (assuming the node where it was instantiated stops dependencies  
that would otherwise remain as zombies).


#### Inference System  

Located in the `_get.py` file, this system aims to select the solver that will provide  
the best performance for a given CNF. It performs inference on the linear regression model  
of each solver contained within it.  

Inference is the process of deriving conclusions from premises.  
In this case, based on the model obtained through linear regression,  
the expected score or efficiency for a given CNF with a specific SAT solver is estimated.  
The inference process is carried out using Microsoft's ONNX-Runtime library.  

sequenceDiagram
    participant SAT as Instancia de SAT-solver
    participant Config as Objeto SolverConfig
    participant Admin as Administrador de SAT-solver
    participant Cliente
    participant Principal as Componente principal
    participant Inferencia as Componente de inferencia
    participant Regresion as Componente de regresion

    Cliente ->> Principal: 1. Envia CNF
    Principal ->> Inferencia: 2. Solicita modelo
    Inferencia ->> Principal: 3. Retorna modelo
    Principal ->> Inferencia: 4. Atributos de CNF
    Inferencia ->> Principal: 5. Interacción
    Principal ->> Admin: 6. Resuelve c/ SAT-solver
    Admin ->> SAT: 7. Computa SAT-solver
    SAT ->> Admin: 8. Resuelve SAT
    Admin ->> Principal: 9. Retorna interpretación
    Principal ->> Inferencia: 10. Incorpora instancia
    Inferencia ->> Principal: 11. Verifica instancia
    Principal ->> Cliente: 12. Retorna el resultado

Below, a sequence diagram  illustrates the scenario in which a client  
requests SAT resolution from the classification service, assuming the model is loaded into memory  
and the selected solver is instantiated.  

##### Agents involved in the previous sequence diagram are as follows:

- **Client**: Requests the resolution of a SAT problem from the service.
- **Main Service Component**: The gRPC server.
- **Inference Component**: Selects the SAT solver using the trained model.
- **Regression Component**: Apart from communicating with the regression service, it holds the latest trained model.
- **SAT-Solver Manager**: Manages the available instances of each SAT solver.
- **SolverConfig Object**: Belongs to the SAT-Solver Manager and controls the instances of a specific SAT solver with a given configuration.
- **SAT-Solver Instance**: An instance of the SAT solver service, which the inference system selects to solve the specific problem.

##### Below are each of the interactions during the sequence:

1. The client requests the service to solve a specific CNF via the gRPC Solve method.
2. The main service component retrieves the model from the regression component, which holds the last trained model by the regression service.
3. The main service component requests the inference component to specify the most effective SAT solver based on the CNF and the model previously provided by the client and the regression component, respectively.
4. The inference component retrieves the CNF parameters, which include: the number of clauses and the number of literals.
5. The inference component selects the SAT solver with the assumed best performance for that number of clauses and literals.
6. The main service component requests the SAT solver manager to resolve the CNF with the proposed SAT solver.
7. The SAT solver manager checks whether it has this specific SAT solver with the required configuration in its registry. If it has it, it proceeds. Otherwise, it would add it and raise an exception.
8. One of the instances of the SAT solver is acquired from the stack of the corresponding solver object. This ensures that another request will not be aware of the instance, as it will not be found in the stack. If there are no instances in the stack, a new one would be created via the process shown in the diagram of Figure 5.
9. The SAT solver manager requests the SAT solver instance to resolve the SAT problem by sending the CNF to it.
10. The SAT solver returns an interpretation or states that it is unsatisfiable, provided that the service's timeout has not been exceeded.
11. The availability of the instance is checked. If there was an issue in the previous step, a request would be made to resolve a simple CNF to verify it. If it fails, the instance would be stopped.
12. After using the instance and verifying that it is active, it is placed back into the stack, making it available for training or other similar requests.
13. The SAT solver manager returns the result to the main service component, which in turn returns it to the client.


##### Singleton Pattern  

The Singleton pattern is a design pattern that restricts the creation of objects belonging to a class  
or the value of a type to a single instance. This limits the creation to only one instance of the classes `train.Session`, `regression.Session`, and `solve.Session`.  

To send the specification of a service via gRPC, the message `Grpc ServiceTransport` is used.  
This optimizes the process by streaming each hash of the specification (one by one) and, finally, the complete specification.  
Additionally, the configuration (if used to request an instance) is sent in just one part.  

When the server receives the stream, it checks the hashes to determine whether it already possesses the service.  
If it does, the server processes the stream without needing to send the full specification.

##### Data Set Format  

The data set format consists of a score for each type of CNF (number of instances * number of clauses)  
along with the number of entries for each score per solver with a specific configuration.  
Its specification is also stored in the data set.  

As seen in Figure 11, the data set stores the information generated during training or delivered to the classification service from external sources.  
It stores the score of each SAT solver for each type of CNF tested.  
The same model is used both to exchange data between the classification and regression services  
and to store the data in each of these two services.


