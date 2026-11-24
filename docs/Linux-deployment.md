# Chapter 7 Linux deployment

1. Provision an Ubuntu Linux VM after confirming the provider and cost. Record the region, distribution and public IPv4 address. Allow TCP 22 from your own public IP. Allow TCP 80 and 443 from the internet. Keep 5432 and 8000 private.
2. Use the VM's public IP. The configuration prompt offers an IP-based hostname from [sslip.io](https://sslip.io/) when you press Enter. You can also enter a provider hostname or a domain you already control that resolves to the VM. Caddy redirects the bare HTTP IP to this hostname for HTTPS. Certificate issuance requires publicly reachable ports 80 and 443.
3. Connect with SSH using the provider's username and your private key. Verify the host fingerprint through the provider console. Install Git, Python 3, Docker Engine and the Compose plugin using the [Ubuntu installation instructions](https://docs.docker.com/engine/install/ubuntu/).
4. After the application has been pushed to the Group 12 repository, run these commands on the fresh VM.

```sh
git clone https://github.com/Yousef-Tadeo-Fadel/supply-chain-ER-diagram-group-12.git
cd supply-chain-ER-diagram-group-12
python3 deploy/start.py
```

Check the redirect and application from a second network. In PowerShell, use `curl.exe` in the following commands. Replace the placeholders with the actual VM address and the hostname selected during setup.

```sh
curl -I http://PUBLIC_IP/
curl --fail https://HOSTNAME/health
```

The first response should redirect to the HTTPS hostname. The second should return a JSON status of `ok`. For network and certificate troubleshooting, see [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https).

The configuration prompt creates separate private login and database credentials. Keep the private directory backed up. Public traffic enters through Caddy. The production manifest removes the database and app host ports.

From a phone on mobile data, open http://PUBLIC_IP and verify the HTTPS dashboard, both private logins, a denied standard-user delete, and an admin delete of a temporary customer. Record the actual address, deployed commit, VM overview, SSH login, container health and external browser screenshots. Mask private details. Rerun the start script to reuse the same private configuration. If the site fails to load, check DNS and inbound 80/443, then run the following from the checkout.

```sh
sudo docker compose --env-file deploy/private/production.env -f compose.yaml -f compose.production.yaml logs --tail 50 edge app
```

Deployment evidence is pending until a VM exists and the external checks succeed.

