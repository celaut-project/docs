Sat-Sorter Repository and Regression & CNF Tools

 __The core service (sat_sorter) automatically selects the most efficient SAT solver based on the structure and size of the CNF-encoded problem, optimizing the resolution of complex constraints.__

This repository contains various services and tools related to solving SAT (Satisfiability) problems and data regression. Below, we describe the key components of the repository:
Sat-Sorter

The Sat-Sorter is the core service of this repository. It is a tool designed to solve SAT problems using advanced classification and sorting algorithms. The Sat-Sorter relies on two essential sub-services:
Regression-CNF

The Regresion-Cnf service is used for data regression. Preprocessing data may be necessary before using the Sat-Sorter for SAT problems. This service handles that task and ensures that the data is prepared for analysis and solving.
Random-Cnf

Random-Cnf is another service that is a dependency of the Sat-Sorter. It is used to generate random CNFs (Conjunctive Normal Forms). These CNFs are useful for training and evaluating the performance of the Sat-Sorter on randomly generated SAT problems.
Solvers

In addition to the components mentioned above, this repository also includes three solvers that can be used to solve SAT problems independently or to compare their performance with the Sat-Sorter.

Testing

To ensure the quality and reliability of the components and tools included in this repository, thorough testing is recommended. You can add unit tests, integration tests, or performance tests as needed.
Execution and Usage

For detailed instructions on how to run and use each of the components and tools mentioned above, please refer to the specific documentation in their respective directories.
