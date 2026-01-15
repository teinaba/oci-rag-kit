# --- Data Sources ---
# リージョンに依存せず全てのOCIサービス（Object Storage等）のIDを取得
data "oci_core_services" "all_services" {
  filter {
    name   = "name"
    values = ["All .* Services In Oracle Services Network"]
    regex  = true
  }
}

# --- VCN ---
resource "oci_core_vcn" "vcn01" {
  cidr_blocks    = ["10.0.0.0/16"]
  compartment_id = var.compartment_ocid
  display_name   = "vcn01"
  dns_label      = "vcn01"
}

# --- Gateways ---
resource "oci_core_internet_gateway" "main_igw" {
  compartment_id = var.compartment_ocid
  display_name   = "Internet-Gateway-vcn01"
  enabled        = true
  vcn_id         = oci_core_vcn.vcn01.id
}

resource "oci_core_nat_gateway" "main_natgw" {
  compartment_id = var.compartment_ocid
  display_name   = "NAT-Gateway-vcn01"
  vcn_id         = oci_core_vcn.vcn01.id
}

resource "oci_core_service_gateway" "main_sgw" {
  compartment_id = var.compartment_ocid
  display_name   = "Service-Gateway-vcn01"
  vcn_id         = oci_core_vcn.vcn01.id
  services {
    service_id = data.oci_core_services.all_services.services[0].id
  }
}

# --- Route Tables ---
# Public Subnet用（VCNデフォルトを利用）
resource "oci_core_default_route_table" "public_route_table" {
  manage_default_resource_id = oci_core_vcn.vcn01.default_route_table_id
  display_name               = "Default-Route-Table-for-Public-Subnet"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.main_igw.id
  }
}

# Private Subnet用
resource "oci_core_route_table" "private_route_table" {
  compartment_id = var.compartment_ocid
  display_name   = "Route-Table-for-Private-Subnet"
  vcn_id         = oci_core_vcn.vcn01.id

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.main_natgw.id
  }

  route_rules {
    destination       = data.oci_core_services.all_services.services[0].cidr_block
    destination_type  = "SERVICE_CIDR_BLOCK"
    network_entity_id = oci_core_service_gateway.main_sgw.id
  }
}

# --- Security Lists ---
# Public Subnet用
resource "oci_core_default_security_list" "public_security_list" {
  manage_default_resource_id = oci_core_vcn.vcn01.default_security_list_id
  display_name               = "Default-Security-List-for-Public-Subnet"

  egress_security_rules {
    destination      = "0.0.0.0/0"
    protocol         = "all"
    stateless        = false
  }

  ingress_security_rules {
    protocol  = "6" # TCP
    source    = "0.0.0.0/0"
    stateless = false
    tcp_options {
      min = 22
      max = 22
    }
  }

  ingress_security_rules {
    protocol  = "1" # ICMP
    source    = "0.0.0.0/0"
    stateless = false
    icmp_options {
      type = 3
      code = 4
    }
  }

  ingress_security_rules {
    protocol  = "1" # ICMP
    source    = "10.0.0.0/16"
    stateless = false
    icmp_options {
      type = 3
      code = -1
    }
  }
}

# Private Subnet用
resource "oci_core_security_list" "private_security_list" {
  compartment_id = var.compartment_ocid
  display_name   = "Security-List-for-Private-Subnet"
  vcn_id         = oci_core_vcn.vcn01.id

  egress_security_rules {
    destination      = "0.0.0.0/0"
    protocol         = "all"
    stateless        = false
  }

  ingress_security_rules {
    protocol  = "1" # ICMP (Path MTU Discovery)
    source    = "0.0.0.0/0"
    stateless = false
    icmp_options {
      type = 3
      code = 4
    }
  }

  ingress_security_rules {
    protocol  = "1" # ICMP (VCN Internal)
    source    = "10.0.0.0/16"
    stateless = false
    icmp_options {
      type = 3
      code = -1
    }
  }
}

# --- Subnets ---
# Public Subnet
resource "oci_core_subnet" "public_subnet" {
  cidr_block      = "10.0.0.0/24"
  compartment_id  = var.compartment_ocid
  display_name    = "Public-Subnet-01"
  vcn_id          = oci_core_vcn.vcn01.id
  dhcp_options_id = oci_core_vcn.vcn01.default_dhcp_options_id
  
  # デフォルトのルート表とセキュリティリストを使用
}

# Private Subnet
resource "oci_core_subnet" "private_subnet" {
  cidr_block                 = "10.0.1.0/24"
  compartment_id             = var.compartment_ocid
  display_name               = "Private-Subnet-01"
  vcn_id                     = oci_core_vcn.vcn01.id
  dhcp_options_id            = oci_core_vcn.vcn01.default_dhcp_options_id
  route_table_id             = oci_core_route_table.private_route_table.id
  security_list_ids          = [oci_core_security_list.private_security_list.id]
  prohibit_internet_ingress  = true
  prohibit_public_ip_on_vnic = true
}
