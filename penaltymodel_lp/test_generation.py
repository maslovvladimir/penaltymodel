from itertools import product
import networkx as nx
import unittest
import penaltymodel.lp as lp


#TODO: add tests on satisfying min_gap. Currently, we're always checking that gap > 0, and passive
# check that gap >= default 2.
class TestPenaltyModelLinearProgramming(unittest.TestCase):
    def verify_gate_bqm(self, bqm, nodes, get_gate_output, ground_energy=0, min_gap=2):
        """Check that all equally valid gate inputs are at ground and that invalid values meet
        threshold (min_gap) requirement.
        """
        for a, b, c in product([-1, 1], repeat=3):
            spin_state = {nodes[0]: a, nodes[1]: b, nodes[2]: c}
            energy = bqm.energy(spin_state)

            if c == get_gate_output(a, b):
                self.assertEqual(ground_energy, energy, "Failed for {}".format(spin_state))
            else:
                self.assertGreaterEqual(energy, ground_energy + min_gap,
                                        "Failed for {}".format(spin_state))

    def test_empty(self):
        with self.assertRaises(ValueError):
            lp.generate_bqm(nx.complete_graph([]), [], [])

    def test_dictionary_input(self):
        # Generate BQM with a dictionary
        nodes = ['a', 'b', 'c']
        ground = 0
        or_gate_values = {(-1, 1, 1): ground,
                          (1, -1, 1): ground,
                          (1, 1, 1): ground,
                          (-1, -1, -1): ground}
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), or_gate_values, nodes)

        self.assertGreater(gap, 0)
        self.verify_gate_bqm(bqm, nodes, max, ground_energy=ground)

    def test_set_input(self):
        # Generate BQM with a set
        nodes = [1, 2, 3]
        and_gate_set = {(-1, -1, -1), (-1, 1, -1), (1, -1, -1), (1, 1, 1)}
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), and_gate_set, nodes)

        self.assertGreater(gap, 0)
        self.verify_gate_bqm(bqm, nodes, min)

    def test_list_input(self):
        # Generate BQM with a list
        nodes = [1, 2, 3]
        nand_gate_list = [(-1, -1, 1), (-1, 1, 1), (1, -1, 1), (1, 1, -1)]
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), nand_gate_list, nodes)

        self.assertGreater(gap, 0)
        self.verify_gate_bqm(bqm, nodes, lambda x, y: -1 * min(x, y))

    def test_min_gap(self):
        # Testing that min_classical_gap parameter works
        def run_same_problem(min_gap):
            nodes = ['a', 'b']
            states = {(-1, -1): -1,
                      (-1, 1): -1,
                      (1, -1): -1}
            return lp.generate_bqm(nx.complete_graph(nodes), states, nodes,
                                   min_classical_gap=min_gap)

        # min_classical_gap=5 should be too large for the problem
        with self.assertRaises(ValueError):
            large_min_gap = 5
            run_same_problem(large_min_gap)

        # Lowering the min_classical_gap should allow a bqm to be found
        smaller_min_gap = 4
        bqm, gap = run_same_problem(smaller_min_gap)
        self.assertEqual(smaller_min_gap, gap)

    def test_linear_energy_range(self):
        # Test linear energy range
        nodes = ['a']
        linear_energy_range = {'a': (-5, -2)}
        config = {1: 96,
                  -1: 104}
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), config, nodes,
                                   linear_energy_ranges=linear_energy_range)

        # Verify that results match expected BQM
        self.assertEqual(100, bqm.offset)
        self.assertEqual(-4, bqm.linear['a'])   # linear bias falls within 'linear_energy_range'

    def test_quadratic_energy_range(self):
        # Test quadratic energy range
        nodes = ['a', 'b']
        quadratic_energy_range = {('a', 'b'): (-130, -120)}
        config = {(-1, -1): -82,
                  (1, 1): -80,
                  (1, -1): 162}
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), config, nodes,
                                   quadratic_energy_ranges=quadratic_energy_range)

        # Verify that results match expected BQM
        self.assertEqual(42, bqm.offset)
        self.assertEqual(-1, bqm.linear['a'])   # Bias within 'linear_energy_range'
        self.assertEqual(2, bqm.linear['b'])    # Bias within 'linear_energy_range'

        # Check that bias is within 'quadratic_energy_range'
        try:
            self.assertEqual(-123, bqm.quadratic[('a', 'b')])
        except KeyError:
            self.assertEqual(-123, bqm.quadratic[('b', 'a')])

    def test_multi_energy_bqm(self):
        # Create BQM for fully determined configuration with no ground states
        configurations = {(-1, -1): -.5, (-1, 1): 3.5, (1, -1): 1.5, (1, 1): 3.5}
        nodes = ['x', 'y']
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), configurations, nodes)

        self.assertGreater(gap, 0)

        # Verify BQM
        for (x, y), expected_energy in configurations.items():
            energy = bqm.energy({'x': x, 'y': y})
            self.assertEqual(expected_energy, energy, "Failed for x:{}, y:{}".format(x, y))

    def test_mixed_specification_truth_table(self):
        # Set a ground state and a valid state with an energy level
        # Note: all other states should be invalid
        configurations = {(-1, -1, 1): 0, (1, -1, 1): 2}
        nodes = ['x', 'y', 'z']
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), configurations, nodes)

        self.assertGreater(gap, 0)

        # Verify BQM
        for i, j, k in product([-1, 1], repeat=3):
            energy = bqm.energy({'x': i, 'y': j, 'z': k})
            if (i, j, k) in configurations.keys():
                self.assertEqual(energy, configurations[(i, j, k)])
            else:
                self.assertGreaterEqual(energy, 2)

    def test_gap_energy_level(self):
        """Check that gap is with respect to the highest energy level provided by user.
        """
        config = {(1, 1): 1, (-1, 1): 0, (1, -1): 0}
        nodes = ['a', 'b']
        bqm, gap = lp.generate_bqm(nx.complete_graph(nodes), config, nodes)

        self.assertEqual(gap, 2)

        # Check specified config
        for a, b in config.keys():
            expected_energy = config[(a, b)]
            energy = bqm.energy({'a': a, 'b': b})
            self.assertEqual(expected_energy, energy)

        # Check unspecified configuration
        # Namely, threshold is gap + max-config-energy (i.e. 2 + 1). Threshold should not be based
        # on gap + smallest-config-energy (i.e. 2 + 0).
        energy = bqm.energy({'a': -1, 'b': -1})
        self.assertEqual(3, energy)

    def test_impossible_bqm(self):
        # Set up xor-gate
        # Note: penaltymodel-lp would need an auxiliary variable in order to handle this;
        #   however, no auxiliaries are provided, hence, it raise an error
        nodes = ['a', 'b', 'c']
        xor_gate_values = {(-1, -1, -1), (-1, 1, 1), (1, -1, 1), (1, 1, -1)}

        # penaltymodel-lp should not be able to handle an xor-gate
        with self.assertRaises(ValueError):
            lp.generate_bqm(nx.complete_graph(nodes), xor_gate_values, nodes)

if __name__ == "__main__":
    unittest.main()
