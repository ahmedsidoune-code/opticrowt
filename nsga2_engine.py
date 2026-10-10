import numpy as np
import random

class Individual:
    def __init__(self, position):
        self.position = position
        self.costs = []
        self.rank = 0
        self.crowding_distance = 0
        self.domination_set = []
        self.dominated_count = 0

def evaluate(position, cm, tm, ym, targets, nt, ns):
    costs = []
    c_val, t_val, y_val = 0, 0, 0
    n_slots = len(position)

    for k in range(n_slots):
        w = position[k] - 1
        s = k // nt
        t = k % nt

        c_val += cm[w][t][s] if w < len(cm) else 0
        if tm: t_val += tm[w][t][s] if w < len(tm) else 0
        if ym: y_val += ym[w][t][s] if w < len(ym) else 0

    c_val /= n_slots
    t_val /= n_slots if tm else 1
    y_val /= n_slots if ym else 1

    for target in targets:
        if target == 'cost': costs.append(c_val)
        elif target == 'time': costs.append(t_val)
        elif target == 'yield': costs.append(-y_val)

    return costs

def dominates(costs_p, costs_q):
    diff = np.array(costs_p) - np.array(costs_q)
    return np.all(diff <= 0) and np.any(diff < 0)

def non_dominated_sorting(pop):
    nPop = len(pop)
    F = [[]]

    for i in range(nPop):
        pop[i].domination_set = []
        pop[i].dominated_count = 0
        for j in range(nPop):
            if i == j: continue
            if dominates(pop[i].costs, pop[j].costs):
                pop[i].domination_set.append(j)
            elif dominates(pop[j].costs, pop[i].costs):
                pop[i].dominated_count += 1
        if pop[i].dominated_count == 0:
            pop[i].rank = 1
            F[0].append(i)

    k = 0
    while True:
        Q = []
        for i in F[k]:
            for j in pop[i].domination_set:
                pop[j].dominated_count -= 1
                if pop[j].dominated_count == 0:
                    pop[j].rank = k + 2
                    Q.append(j)
        if not Q: break
        F.append(Q)
        k += 1
    return pop, F

def calc_crowding_distance(pop, F):
    for front in F:
        if len(front) == 0: continue
        n = len(front)
        for idx in front: pop[idx].crowding_distance = 0

        costs = np.array([pop[idx].costs for idx in front])
        nObj = costs.shape[1]

        for j in range(nObj):
            sorted_idx = np.argsort(costs[:, j])
            pop[front[sorted_idx[0]]].crowding_distance = float('inf')
            pop[front[sorted_idx[-1]]].crowding_distance = float('inf')

            if n > 2:
                for i in range(1, n - 1):
                    if costs[sorted_idx[-1], j] - costs[sorted_idx[0], j] == 0: continue
                    pop[front[sorted_idx[i]]].crowding_distance += (
                        costs[sorted_idx[i+1], j] - costs[sorted_idx[i-1], j]
                    ) / (costs[sorted_idx[-1], j] - costs[sorted_idx[0], j])
    return pop

def crossover(p1, p2):
    n = len(p1)
    pt1, pt2 = sorted(random.sample(range(n), 2))

    c1, c2 = [0]*n, [0]*n
    c1[pt1:pt2+1] = p1[pt1:pt2+1]
    c2[pt1:pt2+1] = p2[pt1:pt2+1]

    rem1 = [g for g in p2 if g not in c1[pt1:pt2+1]]
    rem2 = [g for g in p1 if g not in c2[pt1:pt2+1]]

    idx1, idx2 = 0, 0
    for i in list(range(pt2+1, n)) + list(range(0, pt1)):
        if idx1 < len(rem1): c1[i] = rem1[idx1]; idx1 += 1
        if idx2 < len(rem2): c2[i] = rem2[idx2]; idx2 += 1

    return c1, c2

def mutate(ind, mu=0.2):
    n = len(ind)
    n_mu = int(mu * n)
    y = ind[:]
    for _ in range(n_mu):
        i1, i2 = random.sample(range(n), 2)
        y[i1], y[i2] = y[i2], y[i1]
    return y

def run_nsga2(nw, nt, ns, cm, tm, ym, targets, pop_size=30, max_gen=50):
    nVar = nt * ns
    if nw < nVar:
        nw = nVar

    pop = []
    for _ in range(pop_size):
        pos = random.sample(range(1, nw + 1), nVar)
        ind = Individual(pos)
        ind.costs = evaluate(pos, cm, tm, ym, targets, nt, ns)
        pop.append(ind)

    for it in range(max_gen):
        offspring = []
        for _ in range(pop_size // 2):
            p1, p2 = random.sample(pop, 2)
            c1_pos, c2_pos = crossover(p1.position, p2.position)
            offspring.append(Individual(c1_pos))
            offspring.append(Individual(c2_pos))

        for ind in random.sample(pop, int(0.3 * pop_size)):
            offspring.append(Individual(mutate(ind.position)))

        for ind in offspring:
            ind.costs = evaluate(ind.position, cm, tm, ym, targets, nt, ns)

        pop.extend(offspring)
        pop, F = non_dominated_sorting(pop)
        pop = calc_crowding_distance(pop, F)

        pop.sort(key=lambda x: (x.rank, -x.crowding_distance))
        pop = pop[:pop_size]

    pop, F = non_dominated_sorting(pop)
    pareto_front = [pop[i] for i in F[0]]

    results = []
    for sol in pareto_front:
        shifts = []
        for k in range(ns):
            asn = []
            for j in range(nt):
                w_idx = k * nt + j
                w = sol.position[w_idx]

                cv = cm[w-1][j][k] if w <= len(cm) else 0
                tv = tm[w-1][j][k] if tm and w <= len(tm) else 0
                yv = ym[w-1][j][k] if ym and w <= len(ym) else 0

                a = {"task": j+1, "worker": w, "cost": cv}
                if 'time' in targets: a["time"] = tv
                if 'yield' in targets: a["yield"] = yv
                asn.append(a)
            shifts.append({"shift": k+1, "assignments": asn})

        res_obj = {"shifts": shifts, "objectives": {}}
        for i, t in enumerate(targets):
            val = sol.costs[i]
            if t == 'yield': val = -val
            res_obj["objectives"][t] = round(val, 2)

        worker_view = {}
        for k in range(ns):
            for j in range(nt):
                w_idx = k * nt + j
                w = sol.position[w_idx]

                cv = cm[w-1][j][k] if w <= len(cm) else 0
                tv = tm[w-1][j][k] if tm and w <= len(tm) else 0
                yv = ym[w-1][j][k] if ym and w <= len(ym) else 0

                placement = {"task": j+1, "shift": k+1, "cost": cv}
                if 'time' in targets: placement["time"] = tv
                if 'yield' in targets: placement["yield"] = yv

                if str(w) not in worker_view: worker_view[str(w)] = []
                worker_view[str(w)].append(placement)

        res_obj["workerView"] = worker_view
        results.append(res_obj)

    return results
