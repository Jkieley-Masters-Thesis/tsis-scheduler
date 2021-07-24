#https://kubernetes.io/docs/tasks/tools/install-kubectl-macos/
VERSION=v1.18.10
echo "https://dl.k8s.io/release/$VERSION/bin/linux/386/kubectl"
curl -LO "https://dl.k8s.io/release/$VERSION/bin/linux/386/kubectl"
curl -LO "https://dl.k8s.io/release/$VERSION/bin/linux/386/kubectl.sha256"
echo "$(<kubectl.sha256)  kubectl" | shasum -a 256 --check

chmod +x ./kubectl
sudo mv ./kubectl /usr/local/bin/kubectl
kubectl version --client
