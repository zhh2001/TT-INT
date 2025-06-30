table_claer int_table
table_claer ipv4_lpm
table_set_default int_table add_int_metadata 4
table_set_default ipv4_lpm drop
table_add ipv4_lpm ipv4_forward 10.0.1.0/24 => 00:01:0a:00:03:04 1
table_add ipv4_lpm ipv4_forward 10.0.5.0/24 => 00:01:0a:00:05:04 2