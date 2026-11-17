# ZHU MolEnergy xTB Parameter Dictionary

All absent values are `null` in JSON and “Not reported by this calculation” in CSV. The unmodified `xtb.log` and native `xtbout.json` remain authoritative.

| Field | Meaning | Unit | Source |
|---|---|---|---|
| job_id | Unique local calculation identifier | — | Workbench |
| canonical_smiles, molecular_formula | Chemical identity | — | RDKit input |
| charge, unpaired_electrons, spin_multiplicity | Requested electronic state | e, count | command/job record |
| xtb_version, executable, command | Executable provenance | — | `--version`, invocation |
| optimization_level, solvation_model | Optimization/ALPB setting | — | command and log setup |
| initial_energy_Eh | First optimization-cycle total energy | Eh | `* total energy` |
| final_energy_Eh | Final summary total energy | Eh | `TOTAL ENERGY` |
| energy_change_Eh | final minus initial | Eh | derived |
| *_eV, *_kJ_mol, *_kcal_mol | Converted energies | stated unit | CODATA conversion constants recorded in JSON |
| homo_energy_Eh/eV, lumo_energy_Eh/eV | Frontier orbital energies | Eh/eV | orbital table `(HOMO)/(LUMO)` |
| homo_lumo_gap_eV, fermi_level_* | Gap and Fermi level | eV/Eh | orbital summary |
| dipole_x_D/y_D/z_D/total_D | Full molecular dipole | Debye | molecular dipole `full` row |
| total_charge_e | Reported total charge | e | xTB summary |
| atomic_partial_charges_e | Per-atom charges, input order | e | `charges` and `xtbout.json` |
| wiberg_bond_orders | Atom-index pairs and WBO | — | `wbo` |
| optimization_cycles | ANCOPT cycles to convergence | count | convergence line |
| final_gradient_norm_Eh_per_bohr | Final gradient norm | Eh/a0 | final summary |
| final/max displacement | Last geometry displacement | bohr | final optimization cycle |
| energy/gradient_convergence | Requested criteria | Eh, Eh/a0 | ANCOPT setup |
| scc_converged, final_scc_iterations | Final SCC status/iterations | boolean/count | SCC convergence line |
| energy_terms | Every labeled summary contribution | original unit | `:: ... ::` summary |
| xtbout_json | Complete supported native machine output | mixed | `--json` output |
| warnings | Non-fatal, failure and parser diagnostics | — | raw log/parser |

`xtbout.json` from xTB 6.7.1pre can contain an unescaped quoted Windows command. The parser repairs that single field for structured use while preserving the original file byte-for-byte.
