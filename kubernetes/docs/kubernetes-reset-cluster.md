# Reset Kubernetes Cluster (v1.11.2)
Follow the below instructions to reset Kubernetes cluster v1.11.2.

Log into the master

## Drain and Delete nodes

For every node do:
```
kubectl drain <node>
kubectl delete <node>
```

## Reset control plane
Become sudo: `sudo -s`

```
kubeadm reset
```

```
kubeadm init --pod-network-cidr=10.244.0.0/16
```

Exit sudo. Run the commands to invoke kubectl from none-root

## Apply flannel
```
sudo sysctl net.bridge.bridge-nf-call-iptables=1
```

```
kubectl apply -f https://raw.githubusercontent.com/coreos/flannel/v0.10.0/Documentation/kube-flannel.yml
```

Remember the join command output, you will need it..

## Reset and join nodes

Log into to node

Become sudo: `sudo -s`

## Swap
```
swapoff -a
```
```
kubeadm reset
```
```
sysctl net.bridge.bridge-nf-call-iptables=1
```
```
kubeadm join ....
```

Repeat above for every node

## Tips
It might be that nodes cni subnets are not refreshed yielding to falures in deploying pods. Reboot the nodes and re-deploy pods.