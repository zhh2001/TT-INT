table_clear int_table
table_clear ipv4_lpm
table_clear flow_id_table
table_set_default int_table add_int_metadata 2
table_set_default ipv4_lpm drop
table_add ipv4_lpm ipv4_forward 10.0.1.0/24 => 00:01:0a:00:01:02 1
table_add ipv4_lpm ipv4_forward 10.0.5.0/24 => 00:01:0a:00:03:02 2
table_add flow_id_table set_flow_num 10.0.1.1 10.0.5.5 => 0
