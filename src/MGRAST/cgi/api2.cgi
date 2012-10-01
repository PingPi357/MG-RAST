#!/usr/bin/perl
use CGI;
use JSON;

use Conf;

# create cgi and json objects
my $cgi = new CGI;
my $json = new JSON;
$json = $json->utf8();

# get request method
$ENV{'REQUEST_METHOD'} =~ tr/a-z/A-Z/;
my $request_method = $ENV{'REQUEST_METHOD'};

# get REST parameters
my $abs = $cgi->url(-relative=>1);
if ($abs !~ /\.cgi/) {
  $abs = $cgi->url(-base=>1);
}
my $rest = $cgi->url(-path_info=>1);
$rest =~ s/^.*$abs\/?//;
my @rest_parameters = split m#/#, $rest;
map {$rest[$_] =~ s#forwardslash#/#gi} (0 .. $#rest);

# get the resource
my $resource = shift @rest_parameters;

# get resource list
my $resources = [];
my $resources_hash = {};
my $resource_path = $Conf::api_resource_path."2";
if (! $resource_path) {
  print $cgi->header(-type => 'text/plain',
		     -status => 500,
		     -Access_Control_Allow_Origin => '*' );
  print "ERROR: resource directory not found";
  exit 0;
}

if (opendir(my $dh, $resource_path)) {
  my @res = grep { -f "$resource_path/$_" } readdir($dh);
  closedir $dh;
  @$resources = map { my ($r) = $_ =~ /^(.*)\.pm$/; $r ? $r: (); } @res;
  %$resources_hash = map { $_ => 1 } @$resources;
  
} else {
  if ($cgi->param('POSTDATA') && ! $resource) {
    print $cgi->header(-type => 'application/json',
		       -status => 200,
		       -Access_Control_Allow_Origin => '*' );
    print $json->encode( { jsonrpc => "2.0",
			   id => undef,
			   error => {  code => -32603,
				       message => "Internal error",
				       data => "resource directory offline" } } );
    exit 0;
  } else {
    print $cgi->header(-type => 'text/plain',
		       -status => 500,
		       -Access_Control_Allow_Origin => '*' );
    print "ERROR: resource directory offline";
    exit 0;
  }
}

# check for json rpc
my $json_rpc = $cgi->param('POSTDATA');
$cgi->delete('POSTDATA');
my $json_rpc_id;
my $rpc_request;
my $submethod;
if ($json_rpc && ! $resource) {
  eval { $rpc_request = $json->decode($json_rpc) };
  if ($@) {
    print $cgi->header(-type => 'application/json',
		       -status => 200,
		       -Access_Control_Allow_Origin => '*' );
    print $json->encode( { jsonrpc => "2.0",
			   id => undef,
			   error => {  code => -32700,
				       message => "Parse error",
				       data => $@ } } );
    exit 0;
  }
  
  #    if ($rpc_request->{jsonrpc} && $rpc_request->{jsonrpc} eq "2.0" && $rpc_request->{method}) {
  $json_rpc_id = $rpc_request->{id};
  my $params = $rpc_request->{params};
  if (ref($params) eq 'ARRAY' && ref($params->[0]) eq 'HASH') {
    $params = $params->[0];
  }
  unless (ref($params) eq 'HASH') {
    print $cgi->header(-type => 'application/json',
		       -status => 200,
		       -Access_Control_Allow_Origin => '*' );
    print $json->encode( { jsonrpc => "2.0",
			   id => undef,
			   error => {  code => -32602,
				       message => "Invalid params",
				       data => "only named parameters are accepted" } } );
    exit 0;
  }
  foreach my $key (keys(%$params)) {
    if ($key eq 'id') {
      @rest_parameters = ( $params->{$key} );
    } else {
      $cgi->param($key, $params->{$key});
    }
  }
  (undef, $request_method, $resource, $submethod) = $rpc_request->{method} =~ /^(\w+\.)?(get|post|delete|put)_(\w+)_(\w+)$/;
  $json_rpc = 1;
  # } else {
  # 	print $cgi->header(-type => 'application/json',
  # 		     -status => 200,
  # 		     -Access_Control_Allow_Origin => '*' );
  # 	print $json->encode( { jsonrpc => "2.0",
  # 			       id => undef,
  # 			       error => {  code => -32600,
  # 					   message => "Invalid Request",
  # 					   data => "Malformed JSON structure for JSON RPC 2.0 request, please check the specifications at http://www.jsonrpc.org/specification" } } );
  # 	exit 0;
  # }
}

# check for authentication
my $user;
if ($cgi->http('user_auth')) {
  use Auth;
  $user = Auth::authenticate($cgi->http('user_auth'));
}

# if a resource is passed, call the resources module
if ($resource) {
  if ($resources_hash->{$resource}) {
    my $query = "use resources::$resource; resources::".$resource."::request( { 'rest_parameters' => \\\@rest_parameters, 'method' => \$request_method, 'user' => \$user, 'json_rpc' => \$json_rpc, 'json_rpc_id' => \$json_rpc_id, 'submethod' => \$submethod, 'cgi' => \$cgi } );";
    eval $query;
    if ($@) {
      print $cgi->header(-type => 'text/plain',
			 -status => 500,
			 -Access_Control_Allow_Origin => '*' );
      print "ERROR: resource request failed\n$@\n";
      exit 0;
    }
  } else {
    print $cgi->header(-type => 'text/plain',
		       -status => 500,
		       -Access_Control_Allow_Origin => '*' );
    print "ERROR: resource '$resource' does not exist";
    exit 0;
  }
}
# we are called without a resource, return API information
else {
  my @resource_objects = map { { 'name' => $_, 'url' => $cgi->url.'/'.$_ } } sort @$resources;
  my $content = { version => 1,
		  service => 'MG-RAST',
		  url => $cgi->url,
		  description => 'RESTful Metagenomics RAST object and resource API',
		  documentation => $Conf::cgi_url.'Html/api.html',
		  contact => 'mg-rast@mcs.anl.gov',
		  resources => \@resource_objects };
  print $cgi->header(-type => 'application/json',
		     -status => 200,
		     -Access_Control_Allow_Origin => '*' );
  print $json->encode($content);
  exit 0;
}

sub TO_JSON { return { %{ shift() } }; }

1;
