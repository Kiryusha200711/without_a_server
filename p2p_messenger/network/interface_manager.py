"""
Network Interface Manager for P2P Messenger
Gets all available network interfaces and their IP addresses
"""

import socket
import netifaces
from typing import List, Dict, Tuple, Optional
from ..utils.constants import TCP_PORT


class InterfaceManager:
    """Manages network interface discovery"""
    
    @staticmethod
    def get_all_interfaces() -> List[Dict[str, any]]:
        """Get all network interfaces with their addresses"""
        interfaces = []
        
        try:
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                
                # Get IPv4 addresses
                ipv4_addrs = []
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr.get('addr')
                        if ip and ip != '127.0.0.1':
                            ipv4_addrs.append(ip)
                
                # Get IPv6 addresses
                ipv6_addrs = []
                if netifaces.AF_INET6 in addrs:
                    for addr in addrs[netifaces.AF_INET6]:
                        ip = addr.get('addr')
                        if ip and ip != '::1' and not ip.startswith('fe80::'):
                            ipv6_addrs.append(ip)
                
                if ipv4_addrs or ipv6_addrs:
                    interfaces.append({
                        'name': iface,
                        'ipv4': ipv4_addrs,
                        'ipv6': ipv6_addrs
                    })
        except Exception as e:
            print(f"Error getting interfaces: {e}")
        
        return interfaces
    
    @staticmethod
    def get_all_ips() -> List[Tuple[str, str, int]]:
        """Get all IP addresses with type and priority"""
        ips = []
        interfaces = InterfaceManager.get_all_interfaces()
        
        for iface in interfaces:
            # Add IPv4 addresses
            for ip in iface['ipv4']:
                priority = InterfaceManager._get_priority(ip, 'ipv4')
                ips.append((ip, 'ipv4', priority))
            
            # Add IPv6 addresses
            for ip in iface['ipv6']:
                priority = InterfaceManager._get_priority(ip, 'ipv6')
                ips.append((ip, 'ipv6', priority))
        
        # Sort by priority (lower is better)
        ips.sort(key=lambda x: x[2])
        
        return ips
    
    @staticmethod
    def _get_priority(ip: str, ip_type: str) -> int:
        """Calculate priority for an IP address (lower is better)"""
        # Private IP ranges have higher priority
        if ip.startswith('192.168.'):
            return 10
        elif ip.startswith('10.'):
            return 20
        elif ip.startswith('172.'):
            parts = ip.split('.')
            if len(parts) >= 2:
                second = int(parts[1])
                if 16 <= second <= 31:
                    return 30
        
        # VPN interfaces
        if 'tun' in ip or 'tap' in ip:
            return 40
        
        # Public IPv4
        if ip_type == 'ipv4':
            return 50
        
        # IPv6
        return 60
    
    @staticmethod
    def get_best_ip(target_ip: Optional[str] = None) -> Optional[str]:
        """Get the best local IP for connecting to target"""
        ips = InterfaceManager.get_all_ips()
        
        if not ips:
            return None
        
        if not target_ip:
            # Return the highest priority IP
            return ips[0][0]
        
        # Try to find an IP in the same subnet
        try:
            target_parts = target_ip.split('.')
            if len(target_parts) == 4:
                for ip, ip_type, priority in ips:
                    if ip_type == 'ipv4':
                        ip_parts = ip.split('.')
                        if len(ip_parts) == 4 and ip_parts[:3] == target_parts[:3]:
                            return ip
        except Exception:
            pass
        
        # Return the highest priority IP
        return ips[0][0]
    
    @staticmethod
    def get_external_ip() -> Optional[str]:
        """Get external IP address (using public DNS)"""
        try:
            # Use Google's DNS to determine external IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception as e:
            print(f"Error getting external IP: {e}")
            return None
    
    @staticmethod
    def is_local_ip(ip: str) -> bool:
        """Check if an IP is local (private)"""
        if ip.startswith('192.168.'):
            return True
        if ip.startswith('10.'):
            return True
        if ip.startswith('172.'):
            parts = ip.split('.')
            if len(parts) >= 2:
                second = int(parts[1])
                if 16 <= second <= 31:
                    return True
        if ip == '127.0.0.1' or ip == 'localhost':
            return True
        return False
